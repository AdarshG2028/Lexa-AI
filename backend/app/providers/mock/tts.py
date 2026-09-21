import io
import math
import wave

from app.models import ProviderCheck, SynthesizedSpeech

SAMPLE_RATE = 16000


class MockTextToSpeechProvider:
    """Offline TTS that emits a real, playable 16 kHz mono WAV tone whose length
    scales with the text. It is not speech, but it is valid audio, so the whole
    pipeline including storage and playback can be verified without a key."""

    name = "mock"

    async def synthesize(self, text: str) -> SynthesizedSpeech:
        seconds = max(0.5, min(len(text) / 15.0, 10.0))
        frames = bytearray()
        total = int(SAMPLE_RATE * seconds)
        for i in range(total):
            value = int(8000 * math.sin(2 * math.pi * 220 * i / SAMPLE_RATE))
            frames += value.to_bytes(2, "little", signed=True)

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(SAMPLE_RATE)
            handle.writeframes(bytes(frames))
        return SynthesizedSpeech(
            audio=buffer.getvalue(), format="wav", provider=self.name
        )

    async def check(self) -> ProviderCheck:
        return ProviderCheck(provider=self.name)
