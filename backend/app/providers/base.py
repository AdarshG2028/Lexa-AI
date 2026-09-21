from typing import Protocol, runtime_checkable

from app.models import (
    ChatMessage,
    ChatReply,
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
        self, audio: bytes, filename: str, mime_type: str
    ) -> Transcription: ...

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
