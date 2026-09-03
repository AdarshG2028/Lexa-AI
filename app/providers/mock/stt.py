from app.core.errors import InvalidAudioError
from app.models import ProviderCheck, Transcription

MOCK_TRANSCRIPT = "I go to college yesterday and it was very good."


class MockSpeechToTextProvider:
    """Deterministic offline STT. Does not inspect the audio beyond checking
    that some bytes arrived, so the pipeline can be exercised without a key."""

    name = "mock"

    async def transcribe(
        self, audio: bytes, filename: str, mime_type: str
    ) -> Transcription:
        if not audio:
            raise InvalidAudioError("No audio bytes were provided.")
        return Transcription(text=MOCK_TRANSCRIPT, language="en")

    async def check(self) -> ProviderCheck:
        return ProviderCheck(provider=self.name)
