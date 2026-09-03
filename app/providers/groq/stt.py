from app.config import Settings
from app.core.errors import ProviderBadResponseError
from app.models import ProviderCheck, Transcription
from app.providers.groq.client import GroqClient


class GroqSpeechToTextProvider:
    name = "groq"

    def __init__(self, client: GroqClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.groq_stt_model

    async def transcribe(
        self, audio: bytes, filename: str, mime_type: str
    ) -> Transcription:
        response = await self._client.post(
            "/audio/transcriptions",
            data={"model": self._model, "response_format": "verbose_json"},
            files={"file": (filename, audio, mime_type)},
        )
        try:
            body = response.json()
            return Transcription(
                text=(body["text"] or "").strip(),
                language=body.get("language"),
                duration_seconds=body.get("duration"),
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderBadResponseError(
                "The transcription response was missing expected fields."
            ) from exc

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
