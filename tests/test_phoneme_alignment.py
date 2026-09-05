"""Phoneme alignment and aggregation.

Pure logic, no model: these tests pin down how a mismatch becomes a claim.
"""

import pytest

from app.analysis.phonemes import (
    Alignment,
    ExpectedPhoneme,
    align,
    arpabet_to_ipa,
    practice_words,
)
from app.analysis.pronunciation import MIN_OCCURRENCES, aggregate, score
from app.models import PhonemeSubstitution


def expect(pairs) -> list[ExpectedPhoneme]:
    return [ExpectedPhoneme(phoneme=p, word=w) for p, w in pairs]


# --- ARPAbet to IPA ---

def test_stress_digits_are_stripped():
    assert arpabet_to_ipa("IH1") == arpabet_to_ipa("IH0") == "ɪ"


def test_the_th_sounds_are_distinguished():
    assert arpabet_to_ipa("TH") == "θ"
    assert arpabet_to_ipa("DH") == "ð"


def test_an_unknown_phone_is_rejected_rather_than_guessed():
    assert arpabet_to_ipa("NOTAPHONE") is None


# --- alignment ---

def test_identical_sequences_produce_no_substitutions():
    e = expect([("θ", "think"), ("ɪ", "think"), ("ŋ", "think"), ("k", "think")])
    steps = align(e, ["θ", "ɪ", "ŋ", "k"])

    assert not any(s.is_substitution for s in steps)


def test_a_substitution_is_found_and_tied_to_its_word():
    e = expect([("θ", "think"), ("ɪ", "think"), ("ŋ", "think"), ("k", "think")])
    steps = align(e, ["t", "ɪ", "ŋ", "k"])

    subs = [s for s in steps if s.is_substitution]
    assert len(subs) == 1
    assert (subs[0].expected, subs[0].detected, subs[0].word) == ("θ", "t", "think")


def test_a_dropped_sound_does_not_derail_everything_after_it():
    """Index-by-index comparison would mark every later phoneme wrong."""
    e = expect([("s", "stop"), ("t", "stop"), ("ɑː", "stop"), ("p", "stop")])
    steps = align(e, ["s", "ɑː", "p"])

    subs = [s for s in steps if s.is_substitution]
    assert subs == []
    assert any(s.expected == "t" and s.detected is None for s in steps)


def test_an_inserted_sound_is_recorded_without_blaming_a_word():
    e = expect([("s", "sport"), ("p", "sport")])
    steps = align(e, ["ɪ", "s", "p"])

    assert any(s.expected is None and s.detected == "ɪ" for s in steps)
    assert not any(s.is_substitution for s in steps)


def test_empty_detected_speech_leaves_every_phoneme_unmatched():
    e = expect([("θ", "think")])
    steps = align(e, [])

    assert len(steps) == 1
    assert steps[0].detected is None


def test_alignment_of_nothing_is_empty():
    assert align([], []) == []


# --- practice words ---

def test_practice_words_are_offered_for_common_targets():
    assert "think" in practice_words("θ")
    assert "very" in practice_words("v")


def test_an_unmapped_phoneme_offers_none_rather_than_nonsense():
    assert practice_words("ʔ") == []


# --- aggregation: the strictness rules ---

def sub(expected="θ", detected="t", word="think", confidence=0.9):
    return PhonemeSubstitution(expected=expected, detected=detected,
                               word=word, confidence=confidence)


def test_a_recurring_substitution_becomes_an_issue():
    issues = aggregate([sub(word=w) for w in
                        ("think", "three", "thank", "path")])

    assert len(issues) == 1
    assert issues[0].expected_phoneme == "θ"
    assert issues[0].detected_phoneme == "t"
    assert issues[0].occurrences == 4


def test_a_one_off_mismatch_is_discarded():
    """A single mismatch is more likely an accent or a recogniser slip than
    a habit worth telling someone about."""
    assert aggregate([sub()]) == []
    assert aggregate([sub(), sub(word="three")]) == []


def test_the_threshold_is_exactly_the_documented_one():
    below = aggregate([sub(word=f"w{i}") for i in range(MIN_OCCURRENCES - 1)])
    at = aggregate([sub(word=f"w{i}") for i in range(MIN_OCCURRENCES)])

    assert below == []
    assert len(at) == 1


def test_a_low_confidence_pattern_is_discarded_however_often_it_recurs():
    issues = aggregate([sub(word=f"w{i}", confidence=0.2) for i in range(10)])

    assert issues == []


def test_different_substitutions_are_grouped_separately():
    items = ([sub(word=f"th{i}") for i in range(3)]
             + [sub(expected="v", detected="w", word=f"v{i}") for i in range(3)])
    issues = aggregate(items)

    assert {(i.expected_phoneme, i.detected_phoneme) for i in issues} == {
        ("θ", "t"), ("v", "w")
    }


def test_an_issue_names_the_words_it_came_from_without_repeating_them():
    items = [sub(word="think") for _ in range(3)] + [sub(word="three")]
    issues = aggregate(items)

    assert issues[0].affected_words == ["think", "three"]


def test_issues_carry_practice_words():
    issues = aggregate([sub(word=f"w{i}") for i in range(4)])

    assert "think" in issues[0].practice_words


def test_findings_are_worded_as_a_suggestion_not_an_accusation():
    issues = aggregate([sub(word=f"w{i}") for i in range(4)])

    assert "may be worth practising" in issues[0].explanation


def test_the_most_frequent_pattern_is_reported_first():
    items = ([sub(word=f"th{i}") for i in range(3)]
             + [sub(expected="v", detected="w", word=f"v{i}") for i in range(8)])
    issues = aggregate(items)

    assert issues[0].expected_phoneme == "v"


# --- scoring ---

def test_clean_pronunciation_scores_full_marks():
    assert score([], words=100) == 100


def test_score_falls_as_substitutions_accumulate():
    few = aggregate([sub(word=f"w{i}") for i in range(3)])
    many = aggregate([sub(word=f"w{i}") for i in range(30)])

    assert score(few, 100) > score(many, 100)


def test_score_stays_within_range():
    heavy = aggregate([sub(word=f"w{i}") for i in range(500)])
    assert 0 <= score(heavy, 50) <= 100


def test_no_words_scores_full_marks():
    assert score([], words=0) == 100


# --- notation is not mispronunciation ---

def test_dictionary_and_model_notation_variants_are_not_errors():
    """The model writes /ɐ/ where CMUdict writes /ʌ/. A learner who said the
    word perfectly must not be told they got it wrong."""
    from app.analysis.phonemes import same_sound

    assert same_sound("ʌ", "ɐ")
    assert same_sound("ɚ", "ɜː")
    assert same_sound("iː", "i")
    assert same_sound("ɔː", "ɔːɹ")
    assert same_sound("ɡ", "g")


def test_genuinely_different_sounds_are_still_different():
    from app.analysis.phonemes import same_sound

    assert not same_sound("θ", "t")
    assert not same_sound("v", "w")
    assert not same_sound("ð", "d")
    assert not same_sound("iː", "ɪ")


def test_a_notation_variant_does_not_become_a_substitution():
    e = expect([("ʌ", "cut"), ("ɚ", "her"), ("iː", "see")])
    steps = align(e, ["ɐ", "ɜː", "i"])

    assert not any(s.is_substitution for s in steps)


# --- two further guards against inventing errors ---

def test_reduced_vowels_in_function_words_are_not_judged():
    """Nobody says "and" with the vowel the dictionary gives it."""
    from app.analysis.phonemes import is_reduced_vowel_context

    assert is_reduced_vowel_context("and", "ʌ")
    assert is_reduced_vowel_context("the", "ʌ")
    assert not is_reduced_vowel_context("cat", "æ")


def test_consonants_in_function_words_are_still_judged():
    """Excluding them entirely would remove nearly all evidence for /ð/."""
    from app.analysis.phonemes import is_reduced_vowel_context

    assert not is_reduced_vowel_context("the", "ð")
    assert not is_reduced_vowel_context("that", "ð")


def test_a_vowel_pattern_confined_to_function_words_is_dropped():
    items = [sub(expected="ʌ", detected="æ", word="and") for _ in range(6)]

    assert aggregate(items) == []


def test_a_pattern_seen_in_only_one_word_is_dropped():
    """One recogniser slip repeated is not a pronunciation habit."""
    items = [sub(word="brothers") for _ in range(6)]

    assert aggregate(items) == []


def test_the_same_pattern_across_different_words_is_reported():
    items = ([sub(word="think")] * 3 + [sub(word="three")] * 3)
    issues = aggregate(items)

    assert len(issues) == 1
    assert set(issues[0].affected_words) == {"think", "three"}


# --- thresholds are tunable, not law ---

def test_thresholds_can_be_relaxed_for_short_clips():
    """A 20-second test clip cannot reach the conversation-length defaults."""
    single = [sub(word="think")]

    assert aggregate(single) == []
    relaxed = aggregate(single, min_occurrences=1, min_distinct_words=1)
    assert len(relaxed) == 1
    assert relaxed[0].expected_phoneme == "θ"


def test_relaxing_thresholds_lets_noise_through():
    """The cost of a low threshold, pinned down so it is a choice not a
    surprise: unrelated one-off mismatches all become findings."""
    noise = [
        sub(expected="ʌ", detected="ɪ", word="cut"),
        sub(expected="uː", detected="ɐ", word="food"),
        sub(expected="l", detected="n", word="light"),
    ]

    assert aggregate(noise) == []
    assert len(aggregate(noise, min_occurrences=1, min_distinct_words=1)) == 3


def test_confidence_still_filters_when_occurrence_thresholds_are_relaxed():
    weak = [sub(word="think", confidence=0.2)]

    assert aggregate(weak, min_occurrences=1, min_distinct_words=1) == []
