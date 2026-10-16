import logging
import unicodedata
from difflib import SequenceMatcher

from app.core.errors import AnalysisNotApplicableError
from app.languages import SpokenLanguage, get_language
from app.models import (
    AlternativeKind,
    EnglishAlternative,
    EnglishAlternativesAnalysis,
    Session,
    SessionMode,
    Speaker,
    UserUtterance,
)
from app.providers.base import EnglishAlternativesProvider

logger = logging.getLogger(__name__)

MAX_ITEMS = 12

# The longest span that can be called a word or a phrase. Past this the model
# has translated a clause, which is not what was asked for and is of little
# use to learn from; the prompt says so, and this is what holds if it ignores
# that. Dravidian words carry long suffix chains, so this counts whitespace
# tokens and is deliberately not tight.
MAX_ORIGINAL_WORDS = 6

# How closely a quoted span must match something actually transcribed. Below
# this the item is treated as invented. It is not 1.0 because the model is
# told to copy exactly, and still sometimes tidies a spelling: in the
# agglutinative languages one dropped suffix letter is common, and rejecting
# those would discard genuinely useful items.
MIN_MATCH = 0.8


def collect_utterances(session: Session) -> list[UserUtterance]:
    """What the learner said, one entry per turn, in order.

    Whole turns rather than sentences: the model judges a phrase better with
    its surroundings, and nothing here needs a finding pinned to a sentence.
    """
    return [
        UserUtterance(turn_id=turn.id, text=turn.transcript.strip())
        for turn in session.turns
        if turn.speaker is Speaker.USER and turn.transcript.strip()
    ]


def language_of(session: Session) -> SpokenLanguage:
    """The session's language, or the reason this analysis cannot run."""
    if session.mode is not SessionMode.LANGUAGE_BRIDGE:
        raise AnalysisNotApplicableError(
            "English alternatives are for conversations held in another "
            "language. This one was held in English."
        )
    language = get_language(session.spoken_language)
    if language is None:
        raise AnalysisNotApplicableError(
            "This conversation has no supported spoken language recorded."
        )
    return language


class EnglishAlternativesService:
    """Turns what a learner said in their own language into English
    alternatives they can learn from.

    The provider decides what is worth including. This class decides what is
    allowed to be reported: only spans that really appear in the transcript,
    only genuine English, only once each, and only a handful.
    """

    def __init__(self, provider: EnglishAlternativesProvider) -> None:
        self._provider = provider

    async def analyze(self, session: Session) -> EnglishAlternativesAnalysis:
        language = language_of(session)
        utterances = collect_utterances(session)

        if not utterances:
            return EnglishAlternativesAnalysis(
                session_id=session.id,
                spoken_language=language.code,
                provider=self._provider.name,
                note=(
                    "This conversation has no spoken turns, so there is "
                    "nothing to suggest English for. Speak your turns "
                    f"in {language.name}."
                ),
            )

        proposed = await self._provider.suggest(language, utterances)
        items = clean(proposed, utterances)

        dropped = len(proposed) - len(items)
        if dropped:
            logger.info(
                "Kept %d of %d proposed alternatives for %s session %s.",
                len(items), len(proposed), language.code, session.id,
            )

        note = ""
        if not items:
            note = (
                "Nothing stood out: the words and phrases you used were "
                "mostly everyday ones you will already know in English."
            )
        elif language.accuracy_note:
            note = language.accuracy_note

        return EnglishAlternativesAnalysis(
            session_id=session.id,
            spoken_language=language.code,
            provider=self._provider.name,
            turns_analyzed=len(utterances),
            note=note,
            items=items,
        )


def clean(
    proposed: list[EnglishAlternative], utterances: list[UserUtterance]
) -> list[EnglishAlternative]:
    """Keeps only items that are real, English, distinct and few.

    Each kept item has its `original` replaced by the transcribed text it was
    matched to, so what is shown is always what was actually said - never the
    model's tidied or invented version of it.
    """
    kept: list[EnglishAlternative] = []
    seen: set[str] = set()

    for item in proposed:
        english = item.english.strip()
        if not _is_english(english):
            continue

        match = _locate(item.original, utterances)
        if match is None:
            continue
        original, turn_id = match
        if len(original.split()) > MAX_ORIGINAL_WORDS:
            continue

        key = _normalise(original)
        if key in seen or key == _normalise(english):
            continue
        seen.add(key)

        kept.append(
            EnglishAlternative(
                id=item.id,
                turn_id=turn_id,
                original=original,
                english=english,
                kind=(
                    AlternativeKind.PHRASE
                    if len(original.split()) > 1
                    else AlternativeKind.WORD
                ),
                example=item.example.strip(),
            )
        )
        if len(kept) >= MAX_ITEMS:
            break

    return kept


def _locate(
    quoted: str, utterances: list[UserUtterance]
) -> tuple[str, str] | None:
    """Finds the transcribed words a quoted span refers to.

    Slides a window of the quoted length (and one word either side, since
    recognition sometimes splits or joins words) over every utterance and
    takes the closest. Returns the words as transcribed and their turn, or
    None when nothing is close enough.
    """
    target = _normalise(quoted)
    if not target:
        return None
    width = len(target.split())

    best_ratio = 0.0
    best: tuple[str, str] | None = None

    for utterance in utterances:
        raw = utterance.text.split()
        normal = [_normalise(word) for word in raw]

        for size in sorted({max(1, width - 1), width, width + 1}):
            for start in range(len(raw) - size + 1):
                candidate = " ".join(normal[start : start + size]).strip()
                if not candidate:
                    continue
                ratio = (
                    1.0
                    if candidate == target
                    else SequenceMatcher(None, target, candidate).ratio()
                )
                if ratio > best_ratio:
                    best_ratio = ratio
                    span = " ".join(raw[start : start + size])
                    best = (_trim(span), utterance.turn_id)

    if best_ratio < MIN_MATCH:
        return None
    return best


def _normalise(text: str) -> str:
    """Comparable form: composed, case-folded, with punctuation and invisible
    joiners removed. The zero-width joiners go because recognition emits them
    inconsistently inside Indic conjuncts and they carry no meaning here."""
    composed = unicodedata.normalize("NFC", text).casefold()
    kept = []
    for char in composed:
        category = unicodedata.category(char)
        if category[0] in "PS":
            kept.append(" ")
        elif category == "Cf":
            continue
        else:
            kept.append(char)
    return " ".join("".join(kept).split())


def _trim(text: str) -> str:
    """Strips punctuation from the ends of a span, keeping what is inside."""
    start, end = 0, len(text)
    while start < end and unicodedata.category(text[start])[0] in "PS":
        start += 1
    while end > start and unicodedata.category(text[end - 1])[0] in "PS":
        end -= 1
    return text[start:end]


def _is_english(text: str) -> bool:
    """True when every letter is Latin. A reply still in the learner's own
    script means the model did not do the one thing asked of it."""
    letters = [char for char in text if char.isalpha()]
    return bool(letters) and all(ord(char) < 0x250 for char in letters)
