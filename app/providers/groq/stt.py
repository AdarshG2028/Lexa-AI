from app.config import Settings
from app.core.errors import ProviderBadResponseError
from app.models import ProviderCheck, Transcription, WordTiming
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
            data={
                "model": self._model,
                "response_format": "verbose_json",
                # Word timings are what the fluency analysis is built on, and
                # they cost nothing extra here.
                "timestamp_granularities[]": "word",
            },
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
