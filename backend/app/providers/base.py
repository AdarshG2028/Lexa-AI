from typing import Protocol, runtime_checkable

from app.languages import SpokenLanguage
from app.models import (
    ChatMessage,
    ChatReply,
    EnglishAlternative,
    GrammarIssue,
    PhonemeSubstitution,
    ProviderCheck,
    PronunciationSample,
    SynthesizedSpeech,
    Transcription,
    UserUtterance,
    VocabularyIssue,
    VocabularyObservation,
)


@runtime_checkable
class SpeechToTextProvider(Protocol):
    name: str

    async def transcribe(
        self,
        audio: bytes,
        filename: str,
        mime_type: str,
        language: str | None = None,
    ) -> Transcription:
        """`language` is the code of the language being spoken, when the
        caller knows it. None means the provider's configured default."""
        ...

    async def check(self) -> ProviderCheck:
        """Raise an AppError if unusable; otherwise describe what is configured."""
        ...


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def reply(self, messages: list[ChatMessage]) -> ChatReply: ...

    async def check(self) -> ProviderCheck: ...


@runtime_checkable
class TextToSpeechProvider(Protocol):
    name: str

    async def synthesize(self, text: str) -> SynthesizedSpeech: ...

    async def check(self) -> ProviderCheck: ...


@runtime_checkable
class GrammarAnalysisProvider(Protocol):
    name: str

    async def analyze(self, utterances: list[UserUtterance]) -> list[GrammarIssue]:
        """Finds grammar mistakes in what the user said. Must not alter the
        input; every issue carries its own copy of the original text."""
        ...

    async def check(self) -> ProviderCheck: ...


@runtime_checkable
class VocabularyAnalysisProvider(Protocol):
    name: str

    async def enrich(
        self,
        observations: list[VocabularyObservation],
        utterances: list[UserUtterance],
    ) -> list[VocabularyIssue]:
        """Turns measured word-use observations into advice.

        Counts arrive already measured and must be carried through unchanged;
        the provider supplies alternatives and may add unnatural expressions
        it notices, which are not countable in code.
        """
        ...

    async def check(self) -> ProviderCheck: ...


@runtime_checkable
class PronunciationAnalysisProvider(Protocol):
    """Finds where produced sounds differ from expected ones.

    The rest of the backend does not care whether this is wav2vec2, a forced
    aligner, or an external pronunciation-assessment service.
    """

    name: str

    async def analyze(
        self, samples: list[PronunciationSample]
    ) -> list[PhonemeSubstitution]: ...

    async def check(self) -> ProviderCheck: ...


@runtime_checkable
class EnglishAlternativesProvider(Protocol):
    """Finds what a learner said in their own language that is worth knowing
    the English for.

    Unlike the English-speech analyses this is a judgement no arithmetic can
    make - which words are hard, which phrases do not translate word for
    word - so it is entirely the provider's call. The service around it is
    what keeps that call honest.
    """

    name: str

    async def suggest(
        self, language: SpokenLanguage, utterances: list[UserUtterance]
    ) -> list[EnglishAlternative]:
        """Items arrive without a turn; the service attributes them, because
        the quoted text must be checked against the transcript regardless."""
        ...

    async def check(self) -> ProviderCheck: ...
