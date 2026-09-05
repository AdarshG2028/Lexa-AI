import logging
import re
from collections import Counter

from app.models import (
    FluencyAnalysis,
    FluencyFinding,
    FluencyFindingType,
    Session,
    Speaker,
    Turn,
    WordTiming,
)

logger = logging.getLogger(__name__)

# A gap this long between words is a pause rather than ordinary articulation.
PAUSE_SECONDS = 0.5
LONG_PAUSE_SECONDS = 1.0

# Comfortable conversational English. Outside this band the score starts to
# fall: too slow reads as hesitant, too fast as rushed and hard to follow.
TARGET_WPM_LOW = 110.0
TARGET_WPM_HIGH = 160.0

SINGLE_FILLERS = {
    "um", "uh", "erm", "er", "ah", "hmm", "mm", "eh", "uhh", "umm",
}
PHRASE_FILLERS = [
    "you know", "i mean", "sort of", "kind of", "you see",
    "how to say", "what do you call it",
]
# "like" and "actually" are only fillers in some uses, so they are counted but
# treated as weaker evidence than an outright "um".
SOFT_FILLERS = {"like", "actually", "basically", "literally"}

MAX_FINDINGS = 15


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def user_turns_with_timing(session: Session) -> list[Turn]:
    return [
        turn for turn in session.turns
        if turn.speaker is Speaker.USER and turn.words
    ]


class FluencyAnalysisService:
    """Measures how the user spoke, from audio timings.

    Deliberately has no provider and never calls a language model. Speaking
    rate and pause length are measurements, not opinions, and a model asked
    for them would be guessing at numbers this code can read directly.
    """

    def analyze(self, session: Session) -> FluencyAnalysis:
        timed = user_turns_with_timing(session)

        if not timed:
            return _no_speech(session)

        words: list[WordTiming] = []
        spoken_text: list[str] = []
        pauses: list[float] = []

        for turn in timed:
            words.extend(turn.words)
            spoken_text.append(turn.transcript)
            pauses.extend(_gaps(turn.words))

        # Time is summed per turn: the silence between turns is the AI
        # speaking, not the user hesitating.
        analyzed = sum(_turn_seconds(turn) for turn in timed)
        # Word timings and the measured audio duration come from different
        # places and can disagree. Clamping keeps a mismatch from producing a
        # negative articulation rate.
        articulated = max(0.0, analyzed - sum(pauses))

        text = " ".join(spoken_text)
        fillers = _fillers(text)
        repetitions = _repetitions(timed)
        restarts = _restarts(timed)

        long_pauses = [p for p in pauses if p >= LONG_PAUSE_SECONDS]
        counted_pauses = [p for p in pauses if p >= PAUSE_SECONDS]

        rate = _per_minute(len(words), analyzed)
        articulation = _per_minute(len(words), articulated)

        findings = _findings(fillers, long_pauses, repetitions, restarts)

        return FluencyAnalysis(
            session_id=session.id,
            timed_words=len(words),
            analyzed_seconds=round(analyzed, 2),
            speaking_rate_wpm=round(rate, 1),
            articulation_rate_wpm=round(articulation, 1),
            pause_count=len(counted_pauses),
            long_pause_count=len(long_pauses),
            total_pause_seconds=round(sum(counted_pauses), 2),
            filler_count=sum(fillers.values()),
            repetition_count=sum(c for _, c in repetitions),
            restart_count=len(restarts),
            fluency_score=score(
                rate=rate,
                words=len(words),
                seconds=analyzed,
                long_pauses=len(long_pauses),
                fillers=sum(fillers.values()),
                disfluencies=sum(c for _, c in repetitions) + len(restarts),
            ),
            findings=findings,
        )


def _no_speech(session: Session) -> FluencyAnalysis:
    return FluencyAnalysis(
        session_id=session.id,
        timed_words=0,
        analyzed_seconds=0.0,
        speaking_rate_wpm=0.0,
        articulation_rate_wpm=0.0,
        pause_count=0,
        long_pause_count=0,
        total_pause_seconds=0.0,
        filler_count=0,
        repetition_count=0,
        restart_count=0,
        fluency_score=None,
        note=(
            "This conversation contains no spoken audio, so fluency cannot be "
            "measured. Speak your turns rather than typing them."
        ),
    )


def _turn_seconds(turn: Turn) -> float:
    if turn.user_audio and turn.user_audio.duration_seconds:
        return turn.user_audio.duration_seconds
    return max(0.0, turn.words[-1].end - turn.words[0].start)


def _gaps(words: list[WordTiming]) -> list[float]:
    return [
        round(nxt.start - cur.end, 3)
        for cur, nxt in zip(words, words[1:])
        if nxt.start - cur.end > 0
    ]


def _per_minute(count: int, seconds: float) -> float:
    return (count / seconds) * 60 if seconds > 0 else 0.0


def _fillers(text: str) -> Counter:
    counts: Counter = Counter()
    lowered = text.lower()

    for phrase in PHRASE_FILLERS:
        found = lowered.count(phrase)
        if found:
            counts[phrase] += found

    for token in _tokens(text):
        if token in SINGLE_FILLERS or token in SOFT_FILLERS:
            counts[token] += 1

    return counts


def _repetitions(turns: list[Turn]) -> list[tuple[str, int]]:
    """Immediate repetition of the same word: 'I I think', 'the the book'."""
    counts: Counter = Counter()
    for turn in turns:
        tokens = _tokens(turn.transcript)
        for current, following in zip(tokens, tokens[1:]):
            # "I I went" is the most common repetition of all, so short words
            # are counted too.
            if current == following:
                counts[current] += 1
    return counts.most_common()


def _restarts(turns: list[Turn]) -> list[str]:
    """A phrase begun, abandoned and begun again: 'I want to - I want to go'.

    Detected as the same two-word opening appearing twice close together
    inside one turn, which is what a false start looks like in a transcript.
    """
    found: list[str] = []
    for turn in turns:
        tokens = _tokens(turn.transcript)
        seen: dict[str, int] = {}
        hits: list[tuple[int, str]] = []

        for i in range(len(tokens) - 1):
            pair = f"{tokens[i]} {tokens[i + 1]}"
            previous = seen.get(pair)
            if previous is not None and i - previous <= 6:
                hits.append((i, pair))
            seen[pair] = i

        # "I want to, I want to go" trips both "i want" and "want to" one word
        # apart. That is one false start, not two.
        last = None
        for position, pair in hits:
            if last is None or position - last > 1:
                found.append(pair)
            last = position

    return found


def _findings(
    fillers: Counter,
    long_pauses: list[float],
    repetitions: list[tuple[str, int]],
    restarts: list[str],
) -> list[FluencyFinding]:
    findings: list[FluencyFinding] = []

    for word, count in fillers.most_common():
        findings.append(
            FluencyFinding(
                type=FluencyFindingType.FILLER,
                text=word,
                occurrences=count,
                detail=f"Used {count} time{'s' if count > 1 else ''} as a filler.",
            )
        )

    if long_pauses:
        findings.append(
            FluencyFinding(
                type=FluencyFindingType.LONG_PAUSE,
                text=f"{LONG_PAUSE_SECONDS:g}s or longer",
                occurrences=len(long_pauses),
                detail=(
                    f"Longest was {max(long_pauses):.1f}s. "
                    "Pausing is natural; frequent long pauses mid-sentence "
                    "suggest searching for words."
                ),
            )
        )

    for word, count in repetitions:
        findings.append(
            FluencyFinding(
                type=FluencyFindingType.REPETITION,
                text=word,
                occurrences=count,
                detail=f"Said '{word} {word}' - an immediate repetition.",
            )
        )

    for phrase, count in Counter(restarts).most_common():
        findings.append(
            FluencyFinding(
                type=FluencyFindingType.RESTART,
                text=phrase,
                occurrences=count,
                detail=f"Started '{phrase}' more than once in the same turn.",
            )
        )

    return findings[:MAX_FINDINGS]


def score(
    *,
    rate: float,
    words: int,
    seconds: float,
    long_pauses: int,
    fillers: int,
    disfluencies: int,
) -> int:
    """A 0-100 score from four equally weighted measurements.

    Each part contributes at most 25 points of penalty, so no single habit can
    sink the score on its own and the arithmetic stays explainable:

      rate         how far outside comfortable conversational speed
      pauses       long pauses per minute
      fillers      fillers per 100 words
      disfluency   repetitions and restarts per 100 words
    """
    if words == 0 or seconds <= 0:
        return 100

    minutes = seconds / 60
    per_hundred = words / 100

    if rate < TARGET_WPM_LOW:
        rate_penalty = min(1.0, (TARGET_WPM_LOW - rate) / TARGET_WPM_LOW)
    elif rate > TARGET_WPM_HIGH:
        rate_penalty = min(1.0, (rate - TARGET_WPM_HIGH) / TARGET_WPM_HIGH)
    else:
        rate_penalty = 0.0

    # Four or more long pauses a minute reads as consistently hesitant.
    pause_penalty = min(1.0, (long_pauses / minutes) / 4) if minutes else 0.0
    # Five fillers per hundred words is heavy in conversation.
    filler_penalty = min(1.0, (fillers / per_hundred) / 5) if per_hundred else 0.0
    disfluency_penalty = (
        min(1.0, (disfluencies / per_hundred) / 5) if per_hundred else 0.0
    )

    penalty = 25 * (
        rate_penalty + pause_penalty + filler_penalty + disfluency_penalty
    )
    return max(0, min(100, round(100 - penalty)))
