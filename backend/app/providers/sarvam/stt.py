from app.config import Settings
from app.core.errors import ProviderBadResponseError
from app.models import ProviderCheck, Transcription
from app.providers.sarvam.client import SarvamClient


class SarvamSpeechToTextProvider:
    """Speech-to-text for Indian languages through Sarvam's REST endpoint.

    Sarvam is measurably better than Whisper on Kannada, Tamil and Telugu, and
    it accepts the language as a BCP-47 code instead of guessing. It returns
    no word-level timings (the REST API offers sentence-level chunks only), so
    `words` stays empty. That is acceptable here because the fluency analysis,
    which is the only consumer of timings, is refused for bridge sessions.
    """

    name = "sarvam"

    def __init__(self, client: SarvamClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.sarvam_stt_model
        # Empty means "do not send the field"; the model's own default applies.
        self._mode = settings.sarvam_stt_mode.strip()

    async def transcribe(
        self,
        audio: bytes,
        filename: str,
        mime_type: str,
        language: str | None = None,
    ) -> Transcription:
        data = {"model": self._model}
        if self._mode:
            data["mode"] = self._mode
        if language:
            data["language_code"] = _bcp47(language)

        response = await self._client.post(
            "/speech-to-text",
            data=data,
            files={"file": (filename, audio, mime_type)},
        )
        try:
            body = response.json()
            text = (body.get("transcript") or "").strip()
            detected = body.get("language_code")
        except (ValueError, AttributeError, TypeError) as exc:
            raise ProviderBadResponseError(
                "The Sarvam transcription response was missing expected fields."
            ) from exc

        return Transcription(
            text=text,
            language=detected or (_bcp47(language) if language else None),
        )

    async def check(self) -> ProviderCheck:
        """Sarvam has no model-list endpoint this app can query, so the model
        is verified on first use rather than here. `model_listed=None` means
        "not checked", which the health route treats as healthy."""
        return ProviderCheck(
            provider=self.name,
            model=self._model,
            model_listed=None,
            note=(
                "Sarvam does not expose a model list; the configured model is "
                "verified on the first transcription."
            ),
        )


def _bcp47(language: str) -> str:
    """`hi`, `kn`, `ta`, `te` -> the `xx-IN` codes Sarvam expects."""
    code = language.strip()
    if "-" in code:
        return code
    return f"{code.lower()}-IN"
