"""Grammar analysis: detection, scoring, and the rule that the stored
transcript is never rewritten."""

import pytest

from app.analysis.grammar import GrammarAnalysisService, collect_user_utterances, score
from app.models import (
    GrammarCategory,
    GrammarIssue,
    Session,
    Speaker,
    Turn,
    UserUtterance,
)
from app.providers.mock.grammar import MockGrammarAnalysisProvider


def session_with(*said: str) -> Session:
    session = Session()
    for index, text in enumerate(said):
        session.turns.append(
            Turn(index=index, speaker=Speaker.USER, transcript=text,
                 assistant_response="And then what happened?")
        )
    return session


async def analyze(*said: str):
    service = GrammarAnalysisService(MockGrammarAnalysisProvider())
    return await service.analyze(session_with(*said))


# --- what gets analysed ---

def test_only_the_users_speech_is_collected():
    """The assistant's replies must never be assessed."""
    session = session_with("I go to college yesterday.")
    utterances = collect_user_utterances(session)

    assert len(utterances) == 1
    assert utterances[0].text == "I go to college yesterday."
    assert "And then what happened?" not in [u.text for u in utterances]


def test_empty_utterances_are_skipped():
    session = Session()
    session.turns.append(Turn(index=0, speaker=Speaker.USER, transcript="   "))

    assert collect_user_utterances(session) == []


# --- detection ---

async def test_past_tense_mistake_is_detected():
    result = await analyze("I go to college yesterday.")

    assert result.issues
    issue = result.issues[0]
    assert issue.original == "I go to college yesterday."
    assert issue.corrected == "I went to college yesterday."
    assert issue.category is GrammarCategory.TENSE
    assert "past" in issue.explanation.lower()


async def test_adjective_used_where_an_adverb_belongs():
    result = await analyze("The teacher explained the lesson very good.")

    issue = next(i for i in result.issues
                 if i.category is GrammarCategory.WORD_FORM)
    assert issue.corrected == "The teacher explained the lesson very well."


async def test_subject_verb_agreement_is_detected():
    result = await analyze("He go to school every day.")

    issue = result.issues[0]
    assert issue.category is GrammarCategory.SUBJECT_VERB_AGREEMENT
    assert issue.corrected == "He goes to school every day."


async def test_article_before_a_vowel_is_detected():
    result = await analyze("I ate a apple.")

    issue = result.issues[0]
    assert issue.category is GrammarCategory.ARTICLES
    assert issue.corrected == "I ate an apple."


async def test_correct_english_produces_no_issues():
    result = await analyze("I went to college yesterday and enjoyed the lesson.")

    assert result.issues == []
    assert result.grammar_score == 100


async def test_each_issue_carries_the_turn_it_came_from():
    session = session_with("I go to college yesterday.")
    service = GrammarAnalysisService(MockGrammarAnalysisProvider())
    result = await service.analyze(session)

    assert result.issues[0].turn_id == session.turns[0].id


# --- the transcript must not change ---

async def test_analysis_never_modifies_the_transcript():
    session = session_with("I go to college yesterday.")
    original = session.turns[0].transcript

    await GrammarAnalysisService(MockGrammarAnalysisProvider()).analyze(session)

    assert session.turns[0].transcript == original
    assert session.turns[0].transcript == "I go to college yesterday."


# --- counts and scoring ---

async def test_sentences_and_words_are_counted():
    result = await analyze("I went home. It was fine.")

    assert result.sentences_analyzed == 2
    assert result.words_analyzed == 6


def test_a_clean_conversation_scores_full_marks():
    assert score([], sentences=10) == 100


def test_score_falls_as_flawed_sentences_accumulate():
    def issue(text, confidence=1.0):
        return GrammarIssue(original=text, corrected="fixed", explanation="",
                            confidence=confidence)

    clean = score([], 10)
    one = score([issue("first.")], 10)
    three = score([issue("first."), issue("second."), issue("third.")], 10)

    assert clean > one > three
    assert one == 90
    assert three == 70


def test_an_uncertain_issue_costs_less_than_a_confident_one():
    def issue(confidence):
        return GrammarIssue(original="a", corrected="b", explanation="",
                            confidence=confidence)

    assert score([issue(0.5)], 10) > score([issue(1.0)], 10)


def test_score_never_goes_below_zero():
    issues = [GrammarIssue(original=f"a{i}", corrected=f"b{i}", explanation="",
                           confidence=1.0) for i in range(50)]
    assert score(issues, sentences=2) == 0


def test_a_conversation_with_nothing_to_analyse_scores_full_marks():
    """No evidence of mistakes is not evidence of bad grammar."""
    assert score([], sentences=0) == 100


# --- filtering ---

class StubProvider:
    name = "stub"

    def __init__(self, issues):
        self._issues = issues

    async def analyze(self, utterances):
        return self._issues

    async def check(self):
        from app.models import ProviderCheck
        return ProviderCheck(provider=self.name)


async def test_low_confidence_findings_are_dropped():
    """A coach that invents mistakes is worse than one that misses a few."""
    issues = [
        GrammarIssue(original="a", corrected="b", explanation="", confidence=0.1),
        GrammarIssue(original="c", corrected="d", explanation="", confidence=0.9),
    ]
    result = await GrammarAnalysisService(StubProvider(issues)).analyze(
        session_with("something")
    )

    assert [i.original for i in result.issues] == ["c"]


async def test_no_op_corrections_are_dropped():
    issues = [GrammarIssue(original="same text", corrected="same text",
                           explanation="", confidence=0.9)]
    result = await GrammarAnalysisService(StubProvider(issues)).analyze(
        session_with("something")
    )

    assert result.issues == []


async def test_duplicate_findings_are_collapsed():
    issues = [
        GrammarIssue(original="I go", corrected="I went", explanation="",
                     confidence=0.9),
        GrammarIssue(original="i go", corrected="I WENT", explanation="",
                     confidence=0.8),
    ]
    result = await GrammarAnalysisService(StubProvider(issues)).analyze(
        session_with("something")
    )

    assert len(result.issues) == 1


async def test_issues_are_ordered_by_confidence():
    issues = [
        GrammarIssue(original="a", corrected="b", explanation="", confidence=0.5),
        GrammarIssue(original="c", corrected="d", explanation="", confidence=0.95),
        GrammarIssue(original="e", corrected="f", explanation="", confidence=0.7),
    ]
    result = await GrammarAnalysisService(StubProvider(issues)).analyze(
        session_with("something")
    )

    assert [i.confidence for i in result.issues] == [0.95, 0.7, 0.5]


async def test_an_empty_conversation_analyses_cleanly():
    result = await GrammarAnalysisService(MockGrammarAnalysisProvider()).analyze(
        Session()
    )

    assert result.issues == []
    assert result.grammar_score == 100
    assert result.words_analyzed == 0


def test_several_mistakes_in_one_sentence_count_as_one_flawed_sentence():
    """Otherwise a single bad sentence can sink the whole score."""
    same = [
        GrammarIssue(original="He go and we ate a apple.", corrected="x",
                     explanation="", confidence=0.9),
        GrammarIssue(original="He go and we ate a apple.", corrected="y",
                     explanation="", confidence=0.8),
        GrammarIssue(original="He go and we ate a apple.", corrected="z",
                     explanation="", confidence=0.7),
    ]
    one = [same[0]]

    assert score(same, sentences=3) == score(one, sentences=3)


def test_mistakes_across_different_sentences_do_accumulate():
    issues = [
        GrammarIssue(original="first bad one.", corrected="x",
                     explanation="", confidence=0.9),
        GrammarIssue(original="second bad one.", corrected="y",
                     explanation="", confidence=0.9),
    ]
    assert score(issues[:1], 4) > score(issues, 4)


def test_every_sentence_flawed_scores_near_zero():
    issues = [
        GrammarIssue(original=f"sentence {i}.", corrected="x",
                     explanation="", confidence=1.0)
        for i in range(3)
    ]
    assert score(issues, sentences=3) == 0


# --- one sentence per finding ---

def test_a_multi_sentence_turn_is_split_before_analysis():
    """Issues must quote one sentence, not a whole spoken paragraph."""
    session = session_with(
        "Hello, I go to college yesterday. The teacher explained very good."
    )
    utterances = collect_user_utterances(session)

    assert len(utterances) == 2
    assert utterances[0].text == "Hello, I go to college yesterday."
    assert utterances[1].text == "The teacher explained very good."
    assert all(u.turn_id == session.turns[0].id for u in utterances)


async def test_findings_quote_a_single_sentence(*_):
    result = await analyze(
        "Hello, I go to college yesterday. The teacher explained the lesson very good."
    )

    for issue in result.issues:
        assert issue.original.count(".") <= 1


async def test_the_same_mistake_said_twice_is_reported_once():
    """Typed once and spoken once is still one mistake to work on."""
    result = await analyze(
        "I go to college yesterday.",
        "I go to college yesterday.",
    )

    assert len(result.issues) == 1


async def test_sentence_count_reflects_sentences_not_turns():
    result = await analyze("I went home. It was fine. I slept early.")

    assert result.sentences_analyzed == 3


async def test_a_paragraph_wide_restatement_of_a_finding_is_dropped():
    """Models sometimes quote a whole paragraph for a mistake already
    reported against its sentence. Keep the precise one."""
    issues = [
        GrammarIssue(original="I go to college yesterday.",
                     corrected="I went to college yesterday.",
                     explanation="", category=GrammarCategory.TENSE,
                     confidence=0.96),
        GrammarIssue(
            original="Hello there. I go to college yesterday. It was fine.",
            corrected="Hello there. I went to college yesterday. It was fine.",
            explanation="", category=GrammarCategory.TENSE, confidence=0.95),
    ]
    result = await GrammarAnalysisService(StubProvider(issues)).analyze(
        session_with("something")
    )

    assert len(result.issues) == 1
    assert result.issues[0].original == "I go to college yesterday."


async def test_a_different_mistake_in_the_same_paragraph_is_kept():
    issues = [
        GrammarIssue(original="I go to college yesterday.", corrected="I went.",
                     explanation="", category=GrammarCategory.TENSE,
                     confidence=0.9),
        GrammarIssue(original="I go to college yesterday. He explained good.",
                     corrected="I go to college yesterday. He explained well.",
                     explanation="", category=GrammarCategory.WORD_FORM,
                     confidence=0.9),
    ]
    result = await GrammarAnalysisService(StubProvider(issues)).analyze(
        session_with("something")
    )

    assert len(result.issues) == 2


async def test_a_broad_quote_restating_several_findings_is_dropped():
    """Even relabelled, a paragraph that merely repeats two findings already
    made is noise."""
    issues = [
        GrammarIssue(original="I go to college yesterday.", corrected="I went.",
                     explanation="", category=GrammarCategory.TENSE,
                     confidence=0.96),
        GrammarIssue(original="He explained it very good.",
                     corrected="He explained it very well.",
                     explanation="", category=GrammarCategory.WORD_FORM,
                     confidence=0.95),
        GrammarIssue(
            original="I go to college yesterday. He explained it very good.",
            corrected="I went to college yesterday. He explained it very well.",
            explanation="", category=GrammarCategory.SENTENCE_STRUCTURE,
            confidence=0.95),
    ]
    result = await GrammarAnalysisService(StubProvider(issues)).analyze(
        session_with("something")
    )

    assert len(result.issues) == 2
    assert all(i.original.count(".") == 1 for i in result.issues)
