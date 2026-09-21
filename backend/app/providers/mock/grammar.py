import re

from app.models import GrammarCategory, GrammarIssue, ProviderCheck, UserUtterance

PAST_MARKERS = r"yesterday|last night|last week|last year|ago"

IRREGULAR_PAST = {
    "go": "went", "come": "came", "eat": "ate", "see": "saw", "take": "took",
    "make": "made", "give": "gave", "write": "wrote", "speak": "spoke",
    "meet": "met", "buy": "bought", "think": "thought", "teach": "taught",
}


class MockGrammarAnalysisProvider:
    """Rule-based offline grammar checking.

    Deliberately narrow: a handful of mistakes that learners of English make
    constantly, detected with regular expressions. It is not a substitute for
    the LLM provider, but it finds genuine errors with no API key, which keeps
    the analysis demonstrable and the tests deterministic.
    """

    name = "mock"

    async def analyze(self, utterances: list[UserUtterance]) -> list[GrammarIssue]:
        issues: list[GrammarIssue] = []
        for utterance in utterances:
            for sentence in _sentences(utterance.text):
                issues.extend(_check(sentence, utterance.turn_id))
        return issues

    async def check(self) -> ProviderCheck:
        return ProviderCheck(provider=self.name)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _check(sentence: str, turn_id: str) -> list[GrammarIssue]:
    found: list[GrammarIssue] = []
    for rule in (_past_tense, _adverb_form, _subject_verb, _article_before_vowel):
        issue = rule(sentence)
        if issue is not None:
            issue.turn_id = turn_id
            found.append(issue)
    return found


def _past_tense(sentence: str) -> GrammarIssue | None:
    """A past-time marker with a present-tense verb: 'I go to college yesterday'."""
    if not re.search(PAST_MARKERS, sentence, re.IGNORECASE):
        return None

    for present, past in IRREGULAR_PAST.items():
        pattern = rf"\b(I|we|you|they|he|she|it)\s+{present}\b"
        match = re.search(pattern, sentence, re.IGNORECASE)
        if match:
            corrected = re.sub(
                pattern,
                lambda m: f"{m.group(1)} {past}",
                sentence,
                count=1,
                flags=re.IGNORECASE,
            )
            return GrammarIssue(
                original=sentence,
                corrected=corrected,
                explanation=(
                    f"The sentence refers to the past, so '{present}' should be "
                    f"its past form '{past}'."
                ),
                category=GrammarCategory.TENSE,
                confidence=0.9,
            )
    return None


def _adverb_form(sentence: str) -> GrammarIssue | None:
    """An adjective where an adverb belongs: 'explained the lesson very good'."""
    match = re.search(
        r"\b(explained|explain|speaks?|spoke|did|does|do|works?|worked|"
        r"plays?|played|writes?|wrote)\b(.*?)\bvery good\b",
        sentence,
        re.IGNORECASE,
    )
    if not match:
        return None

    corrected = re.sub(r"\bvery good\b", "very well", sentence, count=1,
                       flags=re.IGNORECASE)
    return GrammarIssue(
        original=sentence,
        corrected=corrected,
        explanation=(
            "'Good' is an adjective. Use the adverb 'well' to describe how "
            "an action was done."
        ),
        category=GrammarCategory.WORD_FORM,
        confidence=0.8,
    )


def _subject_verb(sentence: str) -> GrammarIssue | None:
    """Agreement slips: 'he go', 'they was', 'I is'."""
    checks = [
        (r"\b(he|she|it)\s+(go|come|do|have|make|take|want|like|need|know)\b",
         lambda m: f"{m.group(1)} {_third_person(m.group(2))}",
         "A singular subject needs the -s form of the verb."),
        (r"\b(they|we|you)\s+was\b",
         lambda m: f"{m.group(1)} were",
         "A plural subject takes 'were', not 'was'."),
        (r"\bI\s+(is|are)\b",
         lambda m: "I am",
         "'I' takes 'am'."),
    ]

    for pattern, replace, explanation in checks:
        if re.search(pattern, sentence, re.IGNORECASE):
            corrected = re.sub(pattern, replace, sentence, count=1,
                               flags=re.IGNORECASE)
            if corrected != sentence:
                return GrammarIssue(
                    original=sentence,
                    corrected=corrected,
                    explanation=explanation,
                    category=GrammarCategory.SUBJECT_VERB_AGREEMENT,
                    confidence=0.85,
                )
    return None


def _article_before_vowel(sentence: str) -> GrammarIssue | None:
    """'a apple' instead of 'an apple'."""
    match = re.search(r"\ba\s+([aeiou]\w+)", sentence, re.IGNORECASE)
    if not match:
        return None

    corrected = re.sub(r"\ba\s+([aeiou]\w+)", r"an \1", sentence, count=1,
                       flags=re.IGNORECASE)
    return GrammarIssue(
        original=sentence,
        corrected=corrected,
        explanation=(
            f"Use 'an' before a word starting with a vowel sound, "
            f"as in 'an {match.group(1)}'."
        ),
        category=GrammarCategory.ARTICLES,
        confidence=0.75,
    )


def _third_person(verb: str) -> str:
    if verb.lower() == "have":
        return "has"
    if verb.lower() in ("go", "do"):
        return f"{verb}es"
    return f"{verb}s"
