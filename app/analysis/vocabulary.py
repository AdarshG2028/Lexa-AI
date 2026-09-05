import logging
import re
from collections import Counter

from app.models import (
    Session,
    UserUtterance,
    VocabularyAnalysis,
    VocabularyIssue,
    VocabularyIssueType,
    VocabularyObservation,
)
from app.providers.base import VocabularyAnalysisProvider

logger = logging.getLogger(__name__)

MAX_ISSUES = 12

# Words too common to be worth reporting as "repeated".
STOPWORDS = {
    "a", "about", "after", "all", "also", "am", "an", "and", "any", "are", "as",
    "at", "be", "because", "been", "but", "by", "can", "did", "do", "does",
    "for", "from", "had", "has", "have", "he", "her", "him", "his", "how", "i",
    "if", "in", "is", "it", "its", "just", "me", "my", "no", "not", "of", "on",
    "or", "our", "out", "she", "so", "some", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "to", "too", "up", "us",
    "was", "we", "were", "what", "when", "where", "which", "who", "will",
    "with", "would", "you", "your", "yes", "am", "been", "being", "am",
}

# Serviceable words that a learner leans on instead of reaching for something
# more precise. Flagged sooner than ordinary repeated words.
BASIC_WORDS = {
    "good", "bad", "nice", "thing", "things", "stuff", "very", "really",
    "big", "small", "happy", "sad", "get", "got", "lot", "many", "much",
    "great", "fine", "okay", "interesting",
}


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def _repetition_threshold(total_words: int) -> int:
    """How often a word must appear before repetition is worth mentioning.

    Scales with conversation length: saying "college" three times in eighty
    words is a habit, in eight hundred it is just the topic.
    """
    return max(3, round(total_words / 60))


def observe(utterances: list[UserUtterance]) -> tuple[list[VocabularyObservation], list[str]]:
    """Measures word use. Returns observations and the full word list."""
    all_words: list[str] = []
    for utterance in utterances:
        all_words.extend(_words(utterance.text))

    if not all_words:
        return [], []

    threshold = _repetition_threshold(len(all_words))
    observations: list[VocabularyObservation] = []

    phrase_counts = _phrase_counts(utterances)
    for phrase, count in phrase_counts.most_common():
        if count >= max(2, threshold - 1):
            observations.append(
                VocabularyObservation(
                    type=VocabularyIssueType.REPEATED_PHRASE,
                    text=phrase,
                    occurrences=count,
                    example=_find_example(utterances, phrase),
                )
            )

    counts = Counter(all_words)

    for word, count in counts.most_common():
        if word in STOPWORDS or len(word) < 3:
            continue

        # A phrase already reported hides the word only when it accounts for
        # every use of it. "very good" x3 does not explain "good" x7.
        if any(
            word in o.text.split() and o.occurrences >= count
            for o in observations
        ):
            continue

        is_basic = word in BASIC_WORDS
        limit = 3 if is_basic else threshold
        if count < limit:
            continue

        observations.append(
            VocabularyObservation(
                type=(
                    VocabularyIssueType.BASIC_WORD
                    if is_basic
                    else VocabularyIssueType.REPEATED_WORD
                ),
                text=word,
                occurrences=count,
                example=_find_example(utterances, word),
            )
        )

    observations.sort(key=lambda o: o.occurrences, reverse=True)
    return observations[:MAX_ISSUES], all_words


def _phrase_counts(utterances: list[UserUtterance]) -> Counter:
    """Counts two- and three-word phrases worth reporting.

    A phrase needs at least two substantive words. Without that rule "was
    good" outranks "good", and the learner is told about the wrong half of
    their own sentence.
    """
    counts: Counter = Counter()
    for utterance in utterances:
        words = _words(utterance.text)
        spans: set[tuple[int, int]] = set()

        for size in (3, 2):
            for i in range(len(words) - size + 1):
                start, end = _trim_span(words, i, i + size)
                if end - start >= 2:
                    spans.add((start, end))

        # Windows of different sizes can trim to the same span; count it once.
        for start, end in spans:
            counts[" ".join(words[start:end])] += 1

    # A three-word phrase already covers the two-word phrases inside it.
    kept = Counter()
    longer = [p for p in counts if len(p.split()) == 3 and counts[p] >= 2]
    for phrase, count in counts.items():
        if len(phrase.split()) == 2 and any(phrase in p for p in longer):
            continue
        kept[phrase] = count
    return kept


def _trim_span(words: list[str], start: int, end: int) -> tuple[int, int]:
    """Strips stopwords from both ends of a phrase.

    Reporting "was very good" instead of "very good" tells the learner about
    the wrong part of their own sentence, so phrases are reduced to the words
    that actually carry meaning.
    """
    while start < end and words[start] in STOPWORDS:
        start += 1
    while end > start and words[end - 1] in STOPWORDS:
        end -= 1
    return start, end


def _find_example(utterances: list[UserUtterance], term: str) -> str:
    for utterance in utterances:
        if term in utterance.text.lower():
            return utterance.text
    return utterances[0].text if utterances else ""


class VocabularyAnalysisService:
    """Measures word use, then asks a provider only for better alternatives.

    The split is deliberate. "You said 'very good' seven times" is arithmetic
    and belongs in code, where it is always right. Which word would have been
    better needs language sense, which is what the provider is for.
    """

    def __init__(self, provider: VocabularyAnalysisProvider) -> None:
        self._provider = provider

    async def analyze(self, session: Session) -> VocabularyAnalysis:
        from app.analysis.grammar import collect_user_utterances

        utterances = collect_user_utterances(session)
        observations, all_words = observe(utterances)

        issues: list[VocabularyIssue] = []
        if utterances:
            issues = await self._provider.enrich(observations, utterances)

        unique = len(set(all_words))
        total = len(all_words)

        return VocabularyAnalysis(
            session_id=session.id,
            provider=self._provider.name,
            words_analyzed=total,
            unique_words=unique,
            lexical_diversity=round(unique / total, 3) if total else 0.0,
            vocabulary_score=score(observations, total),
            issues=issues[:MAX_ISSUES],
        )


def score(observations: list[VocabularyObservation], total_words: int) -> int:
    """A 0-100 score based on how much of the speech was needless repetition.

    Only the *excess* counts: using a word up to its threshold is normal, and
    only the occurrences beyond that are charged. When excess repetition
    reaches 15% of everything said, the score is zero.

    Lexical diversity is reported but deliberately not scored. Type-token
    ratio falls as any text gets longer, so scoring it would punish a learner
    for talking more, which is the opposite of what this app wants.
    """
    if total_words <= 0:
        return 100

    threshold = _repetition_threshold(total_words)
    excess = 0
    for observation in observations:
        limit = 3 if observation.type is VocabularyIssueType.BASIC_WORD else threshold
        weight = len(observation.text.split())
        excess += max(0, observation.occurrences - limit) * weight

    load = excess / total_words
    return max(0, min(100, round(100 - min(1.0, load / 0.15) * 100)))
