import io
import wave

from app.core.errors import InvalidAudioError
from app.models import ProviderCheck, Transcription, WordTiming

MOCK_TRANSCRIPT = "I go to college yesterday and it was very good."

# One short, natural utterance per supported language, so a conversation in
# any of them can be exercised end to end with no key and no microphone. They
# are matched by the mock alternatives provider.
MOCK_TRANSCRIPTS = {
    "hi": "मुझे थोड़ा सा समय चाहिए क्योंकि मैं अपने काम को पूरा करना चाहता हूँ।",
    "kn": "ನನಗೆ ಸ್ವಲ್ಪ ಸಮಯ ಬೇಕು ಏಕೆಂದರೆ ನಾನು ನನ್ನ ಕೆಲಸವನ್ನು ಮುಗಿಸಬೇಕು.",
    "ta": "எனக்குக் கொஞ்சம் நேரம் வேண்டும் ஏனென்றால் என் வேலையை முடிக்க வேண்டும்.",
    "te": "నాకు కొంచెం సమయం కావాలి ఎందుకంటే నేను నా పని పూర్తి చేయాలి.",
}


class MockSpeechToTextProvider:
    """Deterministic offline STT. Does not inspect the audio beyond checking
    that some bytes arrived, so the pipeline can be exercised without a key."""

    name = "mock"

    async def transcribe(
        self,
        audio: bytes,
        filename: str,
        mime_type: str,
        language: str | None = None,
    ) -> Transcription:
        if not audio:
            raise InvalidAudioError("No audio bytes were provided.")
        transcript = MOCK_TRANSCRIPTS.get(language or "", MOCK_TRANSCRIPT)
        duration = _wav_seconds(audio)
        words = _words(transcript, duration)
        return Transcription(
            text=transcript,
            language=language or "en",
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
