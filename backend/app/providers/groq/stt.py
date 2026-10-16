from app.config import Settings
from app.core.errors import ProviderBadResponseError
from app.models import ProviderCheck, Transcription, WordTiming
from app.providers.groq.client import GroqClient


class GroqSpeechToTextProvider:
    name = "groq"

    def __init__(self, client: GroqClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.groq_stt_model
        self._language = settings.groq_stt_language
        self._bridge_model = settings.groq_stt_bridge_model

    async def transcribe(
        self,
        audio: bytes,
        filename: str,
        mime_type: str,
        language: str | None = None,
    ) -> Transcription:
        # A caller naming a language other than the configured default is a
        # learner speaking their own language, which gets the model measured
        # to cope with it. Everything else keeps the English-tuned path.
        bridged = bool(language) and language != self._language
        data = {
            "model": self._bridge_model if bridged else self._model,
            "response_format": "verbose_json",
            # Word timings are what the fluency analysis is built on, and
            # they cost nothing extra here.
            "timestamp_granularities[]": "word",
        }
        pinned = language or self._language
        if pinned:
            # Skips Whisper's own language auto-detection, which mis-guesses:
            # it has called Kannada Tamil and Telugu Hindi, and transcribed
            # English as another language's phonetics. The learner told us
            # which language they speak, so there is nothing to guess.
            data["language"] = pinned

        response = await self._client.post(
            "/audio/transcriptions",
            data=data,
            files={"file": (filename, audio, mime_type)},
        )
        try:
            body = response.json()
            return Transcription(
                text=(body["text"] or "").strip(),
                language=body.get("language"),
                duration_seconds=body.get("duration"),
                words=_word_timings(body.get("words")),
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderBadResponseError(
                "The transcription response was missing expected fields."
            ) from exc

    async def check(self) -> ProviderCheck:
        listed = await self._client.list_model_ids()
        missing = [m for m in (self._model, self._bridge_model) if m not in listed]
        return ProviderCheck(
            provider=self.name,
            model=self._model,
            model_listed=not missing,
            note=None if not missing else (
                f"{', '.join(missing)} was not in the provider's model list. "
                "It may have been retired or may not be enabled for this API "
                "key. The bridge model serves conversations held in another "
                "language."
            ),
        )


def _word_timings(raw) -> list[WordTiming]:
    """Reads word timings, skipping any entry that is not usable.

    Timings are a bonus on top of the transcript: a malformed one should cost
    the fluency detail, never the transcription itself.
    """
    if not isinstance(raw, list):
        return []

    words: list[WordTiming] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            word = str(item["word"]).strip()
            start = float(item["start"])
            end = float(item["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if word and end >= start:
            words.append(WordTiming(word=word, start=start, end=end))
    return words
