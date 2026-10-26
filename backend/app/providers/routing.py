from app.models import ProviderCheck, Transcription
from app.providers.base import SpeechToTextProvider


class LanguageRoutingSpeechToTextProvider:
    """Sends a turn to a provider chosen by the language being spoken.

    The app supports one conversation in a learner's own language at a time,
    and the best engine differs by language: Whisper for Hindi and English,
    Sarvam for Kannada, Tamil and Telugu. Routing keeps that choice out of the
    conversation service, which only knows it is transcribing `language`.
    """

    name = "routing"

    def __init__(
        self,
        default: SpeechToTextProvider,
        by_language: dict[str, SpeechToTextProvider],
    ) -> None:
        self._default = default
        self._by_language = {
            code.strip().lower(): provider for code, provider in by_language.items()
        }

    def provider_for(self, language: str | None) -> SpeechToTextProvider:
        if not language:
            return self._default
        return self._by_language.get(language.strip().lower(), self._default)

    async def transcribe(
        self,
        audio: bytes,
        filename: str,
        mime_type: str,
        language: str | None = None,
    ) -> Transcription:
        return await self.provider_for(language).transcribe(
            audio, filename, mime_type, language=language
        )

    async def check(self) -> ProviderCheck:
        """Checks every provider a turn could reach, once each.

        A routing layer hides which engine actually serves a language, so a
        preflight that only checked the default would pass while every Tamil
        turn failed.
        """
        checks: list[ProviderCheck] = []
        seen: set[int] = set()
        for provider in (self._default, *self._by_language.values()):
            if id(provider) in seen:
                continue
            seen.add(id(provider))
            checks.append(await provider.check())

        healthy = all(check.model_listed is not False for check in checks)
        notes = [check.note for check in checks if check.note]
        return ProviderCheck(
            provider=self.name,
            model=None,
            model_listed=healthy,
            note="; ".join(notes) or None,
        )
