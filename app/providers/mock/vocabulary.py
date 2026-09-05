import re

from app.models import (
    ProviderCheck,
    UserUtterance,
    VocabularyIssue,
    VocabularyIssueType,
    VocabularyObservation,
)

THESAURUS = {
    "very good": ["excellent", "outstanding", "impressive", "enjoyable"],
    "good": ["excellent", "solid", "worthwhile", "impressive"],
    "bad": ["poor", "disappointing", "unpleasant", "inadequate"],
    "nice": ["pleasant", "lovely", "delightful", "welcoming"],
    "big": ["large", "substantial", "significant", "considerable"],
    "small": ["compact", "modest", "slight", "minor"],
    "happy": ["glad", "delighted", "pleased", "cheerful"],
    "sad": ["upset", "disappointed", "downhearted"],
    "thing": ["item", "aspect", "detail", "matter"],
    "things": ["items", "aspects", "details", "matters"],
    "stuff": ["material", "belongings", "equipment"],
    "get": ["obtain", "receive", "acquire"],
    "got": ["received", "obtained", "gained"],
    "very": ["extremely", "particularly", "remarkably"],
    "really": ["genuinely", "truly", "particularly"],
    "great": ["excellent", "remarkable", "superb"],
    "interesting": ["fascinating", "intriguing", "thought-provoking"],
    "lot": ["a great deal", "considerably", "plenty"],
    "fine": ["satisfactory", "acceptable", "agreeable"],
    "okay": ["acceptable", "reasonable", "satisfactory"],
}

# Redundant or mis-prepositioned phrases learners commonly carry over.
UNNATURAL = [
    (r"\brevert back\b", "revert", "'Revert' already means to go back."),
    (r"\breturn back\b", "return", "'Return' already means to come back."),
    (r"\brepeat again\b", "repeat", "'Repeat' already means to do it again."),
    (r"\bdiscuss about\b", "discuss", "'Discuss' does not take 'about'."),
    (r"\bexplain about\b", "explain", "'Explain' does not take 'about'."),
    (r"\bcope up with\b", "cope with", "The phrase is 'cope with'."),
    (r"\bmore better\b", "better", "'Better' is already comparative."),
    (r"\bmost easiest\b", "easiest", "'Easiest' is already superlative."),
]


class MockVocabularyAnalysisProvider:
    """Offline vocabulary advice from a fixed thesaurus and a short list of
    redundant phrases. Narrow, but it gives real alternatives with no API key,
    which keeps the analysis demonstrable and the tests deterministic."""

    name = "mock"

    async def enrich(
        self,
        observations: list[VocabularyObservation],
        utterances: list[UserUtterance],
    ) -> list[VocabularyIssue]:
        issues = [
            VocabularyIssue(
                type=o.type,
                text=o.text,
                occurrences=o.occurrences,
                example=o.example,
                suggestions=THESAURUS.get(o.text, []),
                explanation=_explain(o),
            )
            for o in observations
        ]
        return issues + _unnatural(utterances)

    async def check(self) -> ProviderCheck:
        return ProviderCheck(provider=self.name)


def _explain(o: VocabularyObservation) -> str:
    if o.type is VocabularyIssueType.BASIC_WORD:
        return (
            f"'{o.text}' is a serviceable word you used {o.occurrences} times. "
            "A more precise choice would make your point land harder."
        )
    if o.type is VocabularyIssueType.REPEATED_PHRASE:
        return f"You used the phrase '{o.text}' {o.occurrences} times."
    return f"You used '{o.text}' {o.occurrences} times. Try varying it."


def _unnatural(utterances: list[UserUtterance]) -> list[VocabularyIssue]:
    found: list[VocabularyIssue] = []
    seen: set[str] = set()

    for utterance in utterances:
        for pattern, better, why in UNNATURAL:
            match = re.search(pattern, utterance.text, re.IGNORECASE)
            if match and match.group(0).lower() not in seen:
                seen.add(match.group(0).lower())
                found.append(
                    VocabularyIssue(
                        type=VocabularyIssueType.UNNATURAL_EXPRESSION,
                        text=match.group(0),
                        occurrences=1,
                        example=utterance.text,
                        suggestions=[better],
                        explanation=why,
                        confidence=0.9,
                    )
                )
    return found
