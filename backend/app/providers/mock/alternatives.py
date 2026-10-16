from app.languages import SpokenLanguage
from app.models import (
    AlternativeKind,
    EnglishAlternative,
    ProviderCheck,
    UserUtterance,
)

# What the mock recognises, per language. They line up with the canned
# transcripts in the mock speech-to-text provider, which is what makes a whole
# conversation in a supported language runnable offline.
PHRASEBOOK: dict[str, list[tuple[str, str, str]]] = {
    "hi": [
        ("थोड़ा सा समय", "a little time", "I need a little time to think."),
        ("पूरा करना", "to complete", "I want to complete this today."),
    ],
    "kn": [
        ("ಸ್ವಲ್ಪ ಸಮಯ", "a little time", "I need a little time to think."),
        ("ಮುಗಿಸಬೇಕು", "have to finish", "I have to finish my work."),
    ],
    "ta": [
        ("கொஞ்சம் நேரம்", "a little time", "I need a little time to think."),
        ("முடிக்க வேண்டும்", "need to finish", "I need to finish my work."),
    ],
    "te": [
        ("కొంచెం సమయం", "a little time", "I need a little time to think."),
        ("పూర్తి చేయాలి", "have to complete", "I have to complete my work."),
    ],
}


class MockEnglishAlternativesProvider:
    """Offline alternatives from a tiny fixed phrasebook.

    It understands nothing; it recognises a handful of known phrases. That is
    enough to exercise matching, filtering, storage and the report with no
    key, which is the only job it has.
    """

    name = "mock"

    async def suggest(
        self, language: SpokenLanguage, utterances: list[UserUtterance]
    ) -> list[EnglishAlternative]:
        spoken = " ".join(u.text for u in utterances)
        found: list[EnglishAlternative] = []
        for original, english, example in PHRASEBOOK.get(language.code, []):
            if original in spoken:
                found.append(
                    EnglishAlternative(
                        original=original,
                        english=english,
                        kind=AlternativeKind.PHRASE,
                        example=example,
                    )
                )
        return found

    async def check(self) -> ProviderCheck:
        return ProviderCheck(provider=self.name)
