import logging

from app.core.errors import AppError
from app.models import ProviderCheck, SynthesizedSpeech
from app.providers.base import TextToSpeechProvider

logger = logging.getLogger(__name__)


class FallbackTextToSpeechProvider:
    """Tries each provider in order until one produces audio.

    A conversation should not end because a TTS vendor is rate limiting or out
    of credit. The result records which provider actually served the audio, so
    a silent downgrade is still visible to the caller.
    """

    name = "fallback"

    def __init__(self, providers: list[TextToSpeechProvider]) -> None:
        if not providers:
            raise ValueError("A fallback chain needs at least one provider.")
        self._providers = providers

    @property
    def chain(self) -> list[str]:
        return [p.name for p in self._providers]

    async def synthesize(self, text: str) -> SynthesizedSpeech:
        last_error: AppError | None = None

        for provider in self._providers:
            try:
                return await provider.synthesize(text)
            except AppError as exc:
                last_error = exc
                logger.warning(
                    "TTS provider %r failed (%s); trying the next in the chain.",
                    provider.name, exc.code,
                )

        assert last_error is not None
        raise last_error

    async def check(self) -> ProviderCheck:
        primary = self._providers[0]
        result = await primary.check()
        remaining = self.chain[1:]
        if remaining:
            suffix = f"Falls back to: {', '.join(remaining)}."
            result.note = f"{result.note} {suffix}" if result.note else suffix
        return result
