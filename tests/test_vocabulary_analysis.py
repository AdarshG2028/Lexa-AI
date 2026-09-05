"""Vocabulary analysis.

The counting is done in code and must be exactly right; the provider is only
responsible for advice. These tests police that boundary.
"""

import pytest

from app.analysis.vocabulary import VocabularyAnalysisService, observe, score
from app.models import (
    Session,
    Speaker,
    Turn,
    UserUtterance,
    VocabularyIssueType,
    VocabularyObservation,
)
from app.providers.mock.vocabulary import MockVocabularyAnalysisProvider


def utterances(*texts: str) -> list[UserUtterance]:
    return [UserUtterance(turn_id=f"t{i}", text=t) for i, t in enumerate(texts)]


def session_with(*texts: str) -> Session:
    session = Session()
    for index, text in enumerate(texts):
        session.turns.append(
            Turn(index=index, speaker=Speaker.USER, transcript=text,
                 assistant_response="Very good, tell me more about that thing.")
        )
    return session


async def analyze(*texts: str):
    service = VocabularyAnalysisService(MockVocabularyAnalysisProvider())
    return await service.analyze(session_with(*texts))


def find(observations, text):
    return next((o for o in observations if o.text == text), None)


# --- counting ---

def test_a_repeated_basic_word_is_counted():
    obs, _ = observe(utterances(
        "The food was good.", "The movie was good.", "The trip was good.",
    ))

    good = find(obs, "good")
    assert good is not None
    assert good.occurrences == 3
    assert good.type is VocabularyIssueType.BASIC_WORD


def test_a_repeated_phrase_is_counted():
    obs, _ = observe(utterances(
        "It was very good.", "The class was very good.", "Food is very good.",
    ))

    phrase = find(obs, "very good")
    assert phrase is not None
    assert phrase.occurrences == 3
    assert phrase.type is VocabularyIssueType.REPEATED_PHRASE


def test_counts_are_exact_across_many_repetitions():
    """The whole point of counting in code is that it is never approximate."""
    obs, _ = observe(utterances(
        "Cricket is my sport.", "I watch cricket often.", "Cricket on Sundays.",
        "My brother plays cricket.", "Cricket in the evening.",
        "We discussed cricket.", "Cricket again today.",
    ))

    assert find(obs, "cricket").occurrences == 7


def test_stopwords_are_not_reported_as_repetition():
    obs, _ = observe(utterances(*["I am here and it is fine." for _ in range(5)]))

    reported = {o.text for o in obs}
    assert "the" not in reported
    assert "and" not in reported
    assert "is" not in reported


def test_a_word_used_once_is_not_reported():
    obs, _ = observe(utterances("I visited an unusual museum yesterday."))

    assert find(obs, "museum") is None


def test_the_repetition_threshold_scales_with_length():
    """Three mentions in a short answer is a habit; in a long one it is
    just the topic."""
    short = utterances("Cricket is fun.", "I watch cricket.", "Cricket again.")
    obs_short, _ = observe(short)
    assert find(obs_short, "cricket") is not None

    filler = " ".join(f"alpha{i} beta{i}" for i in range(200))
    long = utterances(filler, "Cricket is fun.", "I watch cricket.",
                      "Cricket again.")
    obs_long, _ = observe(long)
    assert find(obs_long, "cricket") is None


def test_an_example_sentence_is_captured_for_each_finding():
    obs, _ = observe(utterances(
        "The food was good.", "The movie was good.", "The trip was good.",
    ))

    assert "good" in find(obs, "good").example


def test_phrases_are_trimmed_to_the_words_that_carry_meaning():
    """"was very good" would point the learner at the wrong half of their
    own sentence."""
    obs, _ = observe(utterances(
        "It was very good.", "The class was very good.", "Food is very good.",
    ))

    texts = {o.text for o in obs}
    assert "very good" in texts
    assert "was very good" not in texts


def test_only_the_users_words_are_counted():
    """The assistant says 'very good' in every reply and must be ignored."""
    result_obs, words = observe(
        [UserUtterance(turn_id="t", text="I enjoyed the lesson.")]
    )
    assert all("very" not in o.text for o in result_obs)
    assert "very" not in words


# --- scoring ---

def test_no_repetition_scores_full_marks():
    assert score([], total_words=100) == 100


def test_an_empty_conversation_scores_full_marks():
    assert score([], total_words=0) == 100


def test_score_falls_as_repetition_grows():
    def obs(count):
        return VocabularyObservation(
            type=VocabularyIssueType.BASIC_WORD, text="good",
            occurrences=count, example="x",
        )

    assert score([obs(4)], 100) > score([obs(10)], 100)


def test_only_excess_repetition_is_charged():
    """Using a word up to its threshold is normal speech, not a fault."""
    at_limit = VocabularyObservation(
        type=VocabularyIssueType.BASIC_WORD, text="good", occurrences=3,
        example="x",
    )
    assert score([at_limit], 100) == 100


def test_score_never_leaves_the_range():
    heavy = [
        VocabularyObservation(type=VocabularyIssueType.BASIC_WORD, text=f"w{i}",
                              occurrences=50, example="x")
        for i in range(10)
    ]
    assert score(heavy, 60) == 0


# --- the assembled analysis ---

async def test_analysis_reports_diversity_without_scoring_it():
    """Type-token ratio falls as any text gets longer, so scoring it would
    punish a learner for talking more."""
    result = await analyze("The food was good.", "The movie was good.",
                           "The trip was good.")

    assert 0 < result.lexical_diversity <= 1
    assert result.unique_words <= result.words_analyzed


async def test_alternatives_are_offered_for_a_weak_word():
    result = await analyze("The food was good.", "The movie was good.",
                           "The trip was good.")

    good = next(i for i in result.issues if i.text == "good")
    assert "excellent" in good.suggestions
    assert good.occurrences == 3


async def test_a_redundant_expression_is_flagged():
    result = await analyze("I will revert back to you tomorrow.")

    issue = next(i for i in result.issues
                 if i.type is VocabularyIssueType.UNNATURAL_EXPRESSION)
    assert issue.text.lower() == "revert back"
    assert issue.suggestions == ["revert"]


async def test_a_wrong_preposition_is_flagged():
    result = await analyze("We will discuss about the project.")

    issue = next(i for i in result.issues
                 if i.type is VocabularyIssueType.UNNATURAL_EXPRESSION)
    assert issue.text.lower() == "discuss about"


async def test_varied_speech_produces_no_repetition_findings():
    result = await analyze(
        "I visited the harbour and photographed the fishing boats.",
        "Afterwards we ate grilled seafood beside the water.",
    )

    repetition = [i for i in result.issues
                  if i.type is not VocabularyIssueType.UNNATURAL_EXPRESSION]
    assert repetition == []
    assert result.vocabulary_score == 100


async def test_an_empty_conversation_analyses_cleanly():
    result = await VocabularyAnalysisService(
        MockVocabularyAnalysisProvider()
    ).analyze(Session())

    assert result.issues == []
    assert result.vocabulary_score == 100
    assert result.words_analyzed == 0
    assert result.lexical_diversity == 0.0


async def test_the_number_of_findings_is_capped():
    """Do not bury the learner in suggestions."""
    text = " ".join(f"{w} {w} {w} {w}" for w in
                    ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot",
                     "golf", "hotel", "india", "juliet", "kilo", "lima",
                     "mike", "november", "oscar", "papa"])
    result = await analyze(text)

    assert len(result.issues) <= 12
