from app.audio.processing import repair_wav_header
from app.config import Settings
from app.core.errors import ProviderBadResponseError
from app.models import ProviderCheck, SynthesizedSpeech
from app.providers.deepgram.client import DeepgramClient

SAMPLE_RATE = 24000


class DeepgramTextToSpeechProvider:
    name = "deepgram"

    def __init__(self, client: DeepgramClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.deepgram_tts_model

    async def synthesize(self, text: str) -> SynthesizedSpeech:
        response = await self._client.post(
            "/v1/speak",
            params={
                "model": self._model,
                "encoding": "linear16",
                "container": "wav",
                "sample_rate": SAMPLE_RATE,
            },
            json={"text": text},
        )
        if not response.content:
            raise ProviderBadResponseError("Speech synthesis returned no audio.")
        return SynthesizedSpeech(
            audio=repair_wav_header(response.content), format="wav", provider=self.name
        )

    async def check(self) -> ProviderCheck:
        """Deepgram exposes no model-listing endpoint, and the only way to
        validate a voice name is to synthesize with it. Health checks run
        often, so this reports the configuration without spending a request."""
        return ProviderCheck(
            provider=self.name,
            model=self._model,
            note="Voice names cannot be validated without a billable request.",
        )
