"""Fluency analysis.

Every number here is a measurement taken from word timings, so the tests use
timings constructed to produce exactly known answers.
"""

import pytest

from app.analysis.fluency import (
    FluencyAnalysisService,
    LONG_PAUSE_SECONDS,
    score,
)
from app.models import (
    AudioRef,
    FluencyFindingType,
    Session,
    Speaker,
    Turn,
    WordTiming,
)


def timed(text: str, *, wpm: float = 120.0, gaps: dict[int, float] | None = None):
    """Word timings for `text` at a chosen pace, with optional extra silence
    inserted after the word at a given index."""
    gaps = gaps or {}
    seconds_per_word = 60.0 / wpm
    words, cursor = [], 0.0
    for i, token in enumerate(text.split()):
        spoken = seconds_per_word * 0.6
        words.append(WordTiming(word=token, start=round(cursor, 3),
                                end=round(cursor + spoken, 3)))
        cursor += seconds_per_word + gaps.get(i, 0.0)
    return words


def spoken_session(*turns) -> Session:
    """Each turn is (text, word timings)."""
    session = Session()
    for index, (text, words) in enumerate(turns):
        duration = words[-1].end - words[0].start if words else 0.0
        session.turns.append(
            Turn(
                index=index, speaker=Speaker.USER, transcript=text, words=words,
                assistant_response="Um, you know, that is very very interesting.",
                user_audio=AudioRef(key=f"a{index}.wav", format="wav",
                                    duration_seconds=round(duration, 3)),
            )
        )
    return session


def analyze(*turns):
    return FluencyAnalysisService().analyze(spoken_session(*turns))


def finding(result, kind):
    return [f for f in result.findings if f.type is kind]


# --- speaking rate ---

def test_speaking_rate_is_measured_from_the_timings():
    text = " ".join(f"word{i}" for i in range(60))
    result = analyze((text, timed(text, wpm=120)))

    assert 115 <= result.speaking_rate_wpm <= 125
    assert result.timed_words == 60


def test_a_slower_speaker_gets_a_lower_rate():
    text = " ".join(f"word{i}" for i in range(40))
    slow = analyze((text, timed(text, wpm=70)))
    fast = analyze((text, timed(text, wpm=140)))

    assert slow.speaking_rate_wpm < fast.speaking_rate_wpm


def test_articulation_rate_excludes_pause_time():
    """Articulation rate answers 'how fast when actually speaking', which is
    higher than overall rate whenever there are pauses."""
    text = " ".join(f"word{i}" for i in range(30))
    result = analyze((text, timed(text, wpm=120, gaps={5: 2.0, 15: 2.0})))

    assert result.articulation_rate_wpm > result.speaking_rate_wpm


# --- pauses ---

def test_a_long_silence_is_counted_as_a_long_pause():
    text = "I went to the market yesterday morning"
    result = analyze((text, timed(text, gaps={2: 1.5})))

    assert result.long_pause_count == 1
    assert result.total_pause_seconds >= 1.5


def test_ordinary_gaps_between_words_are_not_pauses():
    text = " ".join(f"word{i}" for i in range(20))
    result = analyze((text, timed(text, wpm=130)))

    assert result.pause_count == 0
    assert result.long_pause_count == 0


def test_several_long_pauses_are_all_counted():
    text = " ".join(f"word{i}" for i in range(20))
    result = analyze((text, timed(text, gaps={3: 1.2, 8: 1.4, 14: 2.0})))

    assert result.long_pause_count == 3
    assert finding(result, FluencyFindingType.LONG_PAUSE)[0].occurrences == 3


def test_silence_between_turns_is_not_blamed_on_the_user():
    """The gap between turns is the AI talking, not the user hesitating."""
    a = timed("first turn here")
    b = timed("second turn here")
    result = analyze(("first turn here", a), ("second turn here", b))

    assert result.long_pause_count == 0


# --- fillers ---

def test_filler_words_are_counted():
    text = "um I went to the market uh and then um I came back"
    result = analyze((text, timed(text)))

    assert result.filler_count == 3
    um = next(f for f in finding(result, FluencyFindingType.FILLER)
              if f.text == "um")
    assert um.occurrences == 2


def test_filler_phrases_are_counted():
    text = "it was you know quite good and i mean really fine"
    result = analyze((text, timed(text)))

    texts = {f.text for f in finding(result, FluencyFindingType.FILLER)}
    assert "you know" in texts
    assert "i mean" in texts


def test_the_assistant_replies_are_never_analysed():
    """Every scripted reply is full of fillers; none may be counted."""
    text = "a clean sentence with no fillers at all"
    result = analyze((text, timed(text)))

    assert result.filler_count == 0


# --- disfluency ---

def test_an_immediate_word_repetition_is_detected():
    text = "I I went to the the market"
    result = analyze((text, timed(text)))

    assert result.repetition_count == 2
    assert {f.text for f in finding(result, FluencyFindingType.REPETITION)} == {
        "i", "the"
    }


def test_a_false_start_is_detected():
    text = "I want to I want to go home now"
    result = analyze((text, timed(text)))

    assert result.restart_count >= 1
    assert finding(result, FluencyFindingType.RESTART)


def test_a_phrase_repeated_far_apart_is_not_a_false_start():
    text = ("I want to visit the harbour and photograph the boats before "
            "the evening light fades and then I want to eat dinner")
    result = analyze((text, timed(text)))

    assert result.restart_count == 0


# --- no audio ---

def test_a_text_only_conversation_cannot_be_scored():
    """Guessing a fluency score from typed text would be worse than saying
    it cannot be measured."""
    session = Session()
    session.turns.append(Turn(index=0, speaker=Speaker.USER, transcript="typed"))

    result = FluencyAnalysisService().analyze(session)

    assert result.fluency_score is None
    assert result.timed_words == 0
    assert "no spoken audio" in result.note


def test_an_empty_session_cannot_be_scored():
    result = FluencyAnalysisService().analyze(Session())

    assert result.fluency_score is None
    assert result.findings == []


# --- scoring ---

def base(**overrides):
    args = dict(rate=130.0, words=200, seconds=90.0, long_pauses=0,
                fillers=0, disfluencies=0)
    args.update(overrides)
    return score(**args)


def test_comfortable_speech_scores_full_marks():
    assert base() == 100


def test_speaking_too_slowly_costs_points():
    assert base(rate=60.0) < 100


def test_speaking_too_fast_also_costs_points():
    assert base(rate=260.0) < 100


def test_any_rate_inside_the_comfortable_band_is_unpenalised():
    assert base(rate=115.0) == base(rate=155.0) == 100


def test_fillers_reduce_the_score():
    assert base(fillers=20) < base(fillers=2)


def test_long_pauses_reduce_the_score():
    assert base(long_pauses=10) < base(long_pauses=1)


def test_no_single_habit_can_sink_the_score_alone():
    """Each of the four parts is capped at 25 points."""
    assert base(fillers=10_000) >= 75
    assert base(long_pauses=10_000) >= 75


def test_every_problem_at_once_scores_near_zero():
    """Only a speaker producing no words at all reaches exactly zero, so a
    very slow, very hesitant speaker lands just above it."""
    assert base(rate=20.0, long_pauses=500, fillers=500, disfluencies=500) <= 5


def test_score_stays_within_range():
    assert 0 <= base(rate=1.0, long_pauses=99, fillers=99, disfluencies=99) <= 100


def test_one_false_start_is_counted_once():
    """"I want to, I want to go" trips two overlapping word pairs but is a
    single false start."""
    text = "I want to I want to go home"
    result = analyze((text, timed(text)))

    assert result.restart_count == 1


def test_two_separate_false_starts_are_both_counted():
    text = ("I want to I want to go there and later she said she said "
            "it would be fine")
    result = analyze((text, timed(text)))

    assert result.restart_count == 2


def test_articulation_rate_never_goes_negative():
    """Word timings and the measured audio duration come from different
    sources and can disagree; a mismatch must not produce nonsense."""
    text = "one two three four five"
    words = timed(text, wpm=60, gaps={1: 5.0, 3: 5.0})
    session = Session()
    session.turns.append(
        Turn(index=0, speaker=Speaker.USER, transcript=text, words=words,
             user_audio=AudioRef(key="a.wav", format="wav",
                                 duration_seconds=1.0))
    )

    result = FluencyAnalysisService().analyze(session)

    assert result.articulation_rate_wpm >= 0
    assert result.speaking_rate_wpm >= 0
    assert result.fluency_score is not None
