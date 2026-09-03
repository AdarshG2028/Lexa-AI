from typing import Protocol, runtime_checkable

from app.models import (
    ChatMessage,
    ChatReply,
    GrammarIssue,
    ProviderCheck,
    SynthesizedSpeech,
    Transcription,
    UserUtterance,
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
