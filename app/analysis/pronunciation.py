import logging
from collections import defaultdict

from app.analysis.phonemes import is_reduced_vowel_context, practice_words
from app.models import (
    PhonemeSubstitution,
    PronunciationAnalysis,
    PronunciationIssue,
    PronunciationSample,
    Session,
    Speaker,
)
from app.providers.base import PronunciationAnalysisProvider
from app.storage.base import AudioStorage

logger = logging.getLogger(__name__)

# Defaults. A single mismatch is far more likely to be an accent, a recogniser
# slip or a dictionary quirk than a pronunciation habit, so a pattern must
# recur before it is reported. These suit a full conversation; they are
# configurable because a short test clip cannot reach them.
MIN_OCCURRENCES = 3
MIN_CONFIDENCE = 0.55
# A pattern confined to a single word is far more likely to be one recogniser
# slip than a pronunciation habit. A habit shows up across different words.
MIN_DISTINCT_WORDS = 2
MAX_ISSUES = 8


class PronunciationAnalysisService:
    """Turns raw phoneme substitutions into a small set of trustworthy habits.

    The provider hears sounds; this decides what is worth telling a learner.
    Phoneme feedback on accented speech produces false positives easily, so
    the filtering here is deliberately strict: a claim that survives is one
    the same speaker made several times over.
    """

    def __init__(
        self,
        provider: PronunciationAnalysisProvider,
        storage: AudioStorage,
        min_occurrences: int = MIN_OCCURRENCES,
        min_confidence: float = MIN_CONFIDENCE,
        min_distinct_words: int = MIN_DISTINCT_WORDS,
    ) -> None:
        self._provider = provider
        self._storage = storage
        self._min_occurrences = min_occurrences
        self._min_confidence = min_confidence
        self._min_distinct_words = min_distinct_words

    async def analyze(self, session: Session) -> PronunciationAnalysis:
        samples, seconds = await self._collect(session)

        if not samples:
            return PronunciationAnalysis(
                session_id=session.id,
                provider=self._provider.name,
                note=(
                    "This conversation contains no spoken audio, so "
                    "pronunciation cannot be analysed. Speak your turns "
                    "rather than typing them."
                ),
            )

        substitutions = await self._provider.analyze(samples)
        issues = aggregate(
            substitutions,
            min_occurrences=self._min_occurrences,
            min_confidence=self._min_confidence,
            min_distinct_words=self._min_distinct_words,
        )
        words = sum(len(s.transcript.split()) for s in samples)

        return PronunciationAnalysis(
            session_id=session.id,
            provider=self._provider.name,
            analyzed_seconds=round(seconds, 2),
            words_analyzed=words,
            phonemes_analyzed=len(substitutions),
            substitutions_found=len(substitutions),
            pronunciation_score=score(issues, words),
            issues=issues,
            note=(
                ""
                if issues
                else (
                    f"No pattern recurred at least {self._min_occurrences} "
                    f"times across {self._min_distinct_words} different words, "
                    f"so nothing is reported. {len(substitutions)} raw "
                    "mismatches were seen, most of which are usually accent or "
                    "recogniser noise rather than errors."
                )
            ),
        )

    async def _collect(
        self, session: Session
    ) -> tuple[list[PronunciationSample], float]:
        samples: list[PronunciationSample] = []
        seconds = 0.0

        for turn in session.turns:
            if turn.speaker is not Speaker.USER or turn.user_audio is None:
                continue
            if not turn.transcript.strip():
                continue

            try:
                audio = await self._storage.load(turn.user_audio.key)
            except Exception as exc:
                logger.warning("Could not read audio for turn %s: %s", turn.id, exc)
                continue

            samples.append(
                PronunciationSample(
                    turn_id=turn.id, transcript=turn.transcript, audio=audio
                )
            )
            seconds += turn.user_audio.duration_seconds or 0.0

        return samples, seconds


def aggregate(
    substitutions: list[PhonemeSubstitution],
    *,
    min_occurrences: int = MIN_OCCURRENCES,
    min_confidence: float = MIN_CONFIDENCE,
    min_distinct_words: int = MIN_DISTINCT_WORDS,
) -> list[PronunciationIssue]:
    """Groups substitutions into recurring patterns, discarding one-offs.

    Grouping by the (expected, detected) pair is what turns scattered noise
    into a claim worth making: "/θ/ became /t/ six times, in these words".
    """
    grouped: dict[tuple[str, str], list[PhonemeSubstitution]] = defaultdict(list)
    for item in substitutions:
        if is_reduced_vowel_context(item.word, item.expected):
            continue
        grouped[(item.expected, item.detected)].append(item)

    issues: list[PronunciationIssue] = []
    for (expected, detected), items in grouped.items():
        if len(items) < min_occurrences:
            continue

        confidence = sum(i.confidence for i in items) / len(items)
        if confidence < min_confidence:
            continue

        words: list[str] = []
        for item in items:
            if item.word and item.word not in words:
                words.append(item.word)

        if len(words) < min_distinct_words:
            continue

        issues.append(
            PronunciationIssue(
                expected_phoneme=expected,
                detected_phoneme=detected,
                occurrences=len(items),
                confidence=round(confidence, 3),
                affected_words=words[:6],
                practice_words=practice_words(expected),
                explanation=(
                    f"/{expected}/ sounded closer to /{detected}/ in "
                    f"{len(items)} words. This may be worth practising."
                ),
            )
        )

    issues.sort(key=lambda i: (i.occurrences, i.confidence), reverse=True)
    return issues[:MAX_ISSUES]


def score(issues: list[PronunciationIssue], words: int) -> int:
    """A 0-100 score based on how much of the speech carried a recurring
    substitution.

    Only reported issues count, so the score reflects the same evidence the
    learner is shown rather than a hidden tally of low-confidence guesses.
    """
    if words <= 0:
        return 100

    weighted = sum(issue.occurrences * issue.confidence for issue in issues)
    load = weighted / words
    return max(0, min(100, round(100 - min(1.0, load / 0.25) * 100)))
