import logging
import re

from app.models import (
    GrammarAnalysis,
    GrammarIssue,
    Session,
    Speaker,
    UserUtterance,
)
from app.providers.base import GrammarAnalysisProvider

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.4
MAX_ISSUES = 25


def collect_user_utterances(session: Session) -> list[UserUtterance]:
    """Every sentence the user spoke, in order.

    The assistant's speech is excluded: the point is to assess the learner.

    A single spoken turn often contains several sentences, so turns are split
    before analysis. That keeps each reported issue anchored to one sentence
    rather than quoting a whole paragraph back at the user, and it lets
    duplicate findings be recognised as duplicates.
    """
    utterances: list[UserUtterance] = []
    for turn in session.turns:
        if turn.speaker is not Speaker.USER:
            continue
        for sentence in _split_sentences(turn.transcript):
            if sentence.strip():
                utterances.append(
                    UserUtterance(turn_id=turn.id, text=sentence.strip())
                )
    return utterances


class GrammarAnalysisService:
    """Runs grammar analysis over a conversation and scores it.

    The provider finds issues; scoring stays here and is deterministic, so the
    same conversation always scores the same and the number can be explained
    without reference to a model's opinion.
    """

    def __init__(self, provider: GrammarAnalysisProvider) -> None:
        self._provider = provider

    async def analyze(self, session: Session) -> GrammarAnalysis:
        utterances = collect_user_utterances(session)
        issues = await self._provider.analyze(utterances) if utterances else []
        issues = _clean(issues)

        sentences = len(utterances)
        words = sum(len(_words(u.text)) for u in utterances)

        return GrammarAnalysis(
            session_id=session.id,
            provider=self._provider.name,
            sentences_analyzed=sentences,
            words_analyzed=words,
            grammar_score=score(issues, sentences),
            issues=issues,
        )


def _clean(issues: list[GrammarIssue]) -> list[GrammarIssue]:
    """Drops no-op corrections, low-confidence guesses and duplicates.

    Low confidence is filtered rather than shown, because a speech coach that
    invents mistakes is worse than one that misses a few.
    """
    seen: set[tuple[str, str]] = set()
    candidates: list[GrammarIssue] = []

    for issue in issues:
        if issue.confidence < MIN_CONFIDENCE:
            continue
        if issue.original.strip() == issue.corrected.strip():
            continue

        key = (issue.original.strip().lower(), issue.corrected.strip().lower())
        if key in seen:
            continue

        seen.add(key)
        candidates.append(issue)

    kept = _prefer_narrowest(candidates)
    kept.sort(key=lambda i: i.confidence, reverse=True)
    return kept[:MAX_ISSUES]


def _prefer_narrowest(issues: list[GrammarIssue]) -> list[GrammarIssue]:
    """Drops findings that restate a mistake already reported more precisely.

    Models do not always respect the instruction to quote one sentence, so the
    same error can come back twice: once quoting its sentence and once quoting
    a whole paragraph containing it. Showing a learner both is noise, and the
    shorter quote is the more useful one.
    """
    by_length = sorted(issues, key=lambda i: len(i.original))
    kept: list[GrammarIssue] = []

    for issue in by_length:
        text = issue.original.strip().lower()
        contained = [
            other for other in kept
            if other.original.strip().lower() in text
        ]

        # The same mistake, quoted more widely.
        same_mistake = any(o.category is issue.category for o in contained)
        # A broad quote that merely restates several findings already made.
        restates_several = len(contained) >= 2

        if not (same_mistake or restates_several):
            kept.append(issue)

    return kept


def score(issues: list[GrammarIssue], sentences: int) -> int:
    """A 0-100 score: the proportion of sentences that contained a mistake.

    Issues are grouped by the sentence they came from, so a sentence with
    three errors in it is still one flawed sentence rather than three. Each
    flawed sentence costs the confidence of its strongest finding, so an
    uncertain guess hurts less than a definite error.

    A conversation with nothing to analyse scores 100 rather than 0: no
    evidence of mistakes is not evidence of bad grammar.
    """
    if sentences <= 0:
        return 100

    worst_per_sentence: dict[str, float] = {}
    for issue in issues:
        key = issue.original.strip().lower()
        worst_per_sentence[key] = max(
            worst_per_sentence.get(key, 0.0), issue.confidence
        )

    ratio = min(1.0, sum(worst_per_sentence.values()) / sentences)
    return max(0, min(100, round(100 - ratio * 100)))


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z']+", text)
