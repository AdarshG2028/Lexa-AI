from app.audio.processing import repair_wav_header
from app.config import Settings
from app.core.errors import ProviderBadResponseError
from app.models import ProviderCheck, SynthesizedSpeech
from app.providers.groq.client import GroqClient


class GroqTextToSpeechProvider:
    name = "groq"

    def __init__(self, client: GroqClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.groq_tts_model
        self._voice = settings.groq_tts_voice
        self._format = settings.groq_tts_format

    async def synthesize(self, text: str) -> SynthesizedSpeech:
        response = await self._client.post(
            "/audio/speech",
            json={
                "model": self._model,
                "voice": self._voice,
                "input": text,
                "response_format": self._format,
            },
        )
        if not response.content:
            raise ProviderBadResponseError("Speech synthesis returned no audio.")
        audio = response.content
        if self._format == "wav":
            audio = repair_wav_header(audio)
        return SynthesizedSpeech(
            audio=audio, format=self._format, provider=self.name
        )

    async def check(self) -> ProviderCheck:
        listed = await self._client.list_model_ids()
        found = self._model in listed
        return ProviderCheck(
            provider=self.name,
            model=self._model,
            model_listed=found,
            note=None if found else (
                "This model ID was not in the provider's model list. It may "
                "have been retired or may not be enabled for this API key."
            ),
        )
