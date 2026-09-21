import io
import wave

from app.core.errors import InvalidAudioError
from app.models import ProviderCheck, Transcription, WordTiming

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
        duration = _wav_seconds(audio)
        words = _words(MOCK_TRANSCRIPT, duration)
        return Transcription(
            text=MOCK_TRANSCRIPT,
            language="en",
            duration_seconds=duration or (words[-1].end if words else 0.0),
            words=words,
        )

    async def check(self) -> ProviderCheck:
        return ProviderCheck(provider=self.name)


def _wav_seconds(audio: bytes) -> float:
    try:
        with wave.open(io.BytesIO(audio), "rb") as handle:
            return handle.getnframes() / handle.getframerate()
    except Exception:
        return 0.0


def _words(text: str, duration: float = 0.0, wpm: float = 130.0) -> list[WordTiming]:
    """Evenly paced timings so the fluency pipeline has something to measure
    offline.

    When the real audio duration is known the words are spread across it, so
    the timings agree with the stored audio instead of contradicting it.
    """
    tokens = text.split()
    seconds_per_word = (
        duration / len(tokens) if duration > 0 and tokens else 60.0 / wpm
    )
    timings: list[WordTiming] = []
    cursor = 0.0
    for token in text.split():
        spoken = seconds_per_word * 0.75
        timings.append(
            WordTiming(word=token, start=round(cursor, 3),
                       end=round(cursor + spoken, 3))
        )
        cursor += seconds_per_word
    return timings
