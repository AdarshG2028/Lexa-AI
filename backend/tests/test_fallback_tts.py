"""The fallback chain exists so a TTS outage or exhausted quota downgrades the
voice instead of ending the conversation."""

import pytest

from app.config import Settings
from app.core.errors import ProviderUnavailableError, ProviderTimeoutError
from app.models import ProviderCheck, SynthesizedSpeech
from app.providers.fallback import FallbackTextToSpeechProvider
from app.providers.mock.tts import MockTextToSpeechProvider
from app.providers.registry import ProviderRegistry


class FailingTTS:
    def __init__(self, name: str, error: Exception) -> None:
        self.name = name
        self._error = error
        self.calls = 0

    async def synthesize(self, text: str) -> SynthesizedSpeech:
        self.calls += 1
        raise self._error

    async def check(self) -> ProviderCheck:
        return ProviderCheck(provider=self.name)


async def test_first_working_provider_serves_the_audio():
    primary = MockTextToSpeechProvider()
    never = FailingTTS("never", ProviderUnavailableError())
    chain = FallbackTextToSpeechProvider([primary, never])

    speech = await chain.synthesize("hello")

    assert speech.provider == "mock"
    assert never.calls == 0


async def test_falls_through_to_the_next_provider_on_failure():
    broken = FailingTTS("deepgram", ProviderUnavailableError())
    chain = FallbackTextToSpeechProvider([broken, MockTextToSpeechProvider()])

    speech = await chain.synthesize("hello")

    assert broken.calls == 1
    assert speech.provider == "mock"
    assert speech.audio


async def test_tries_every_provider_before_giving_up():
    first = FailingTTS("deepgram", ProviderUnavailableError())
    second = FailingTTS("groq", ProviderTimeoutError())

    with pytest.raises(ProviderTimeoutError):
        await FallbackTextToSpeechProvider([first, second]).synthesize("hello")

    assert first.calls == 1
    assert second.calls == 1


async def test_check_reports_the_rest_of_the_chain():
    chain = FallbackTextToSpeechProvider(
        [MockTextToSpeechProvider(), FailingTTS("groq", ProviderUnavailableError())]
    )
    result = await chain.check()

    assert "groq" in result.note


def test_registry_builds_a_chain_from_configuration():
    settings = Settings(
        tts_provider="groq",
        tts_fallback_providers="mock",
        groq_api_key="test-key",
    )
    provider = ProviderRegistry(settings).text_to_speech()

    assert provider.chain == ["groq", "mock"]


def test_registry_returns_a_bare_provider_when_no_fallbacks_configured():
    provider = ProviderRegistry(Settings(tts_provider="mock")).text_to_speech()
    assert provider.name == "mock"


def test_unconfigured_fallback_is_skipped_not_fatal():
    """deepgram has no key here, so it must drop out of the chain silently."""
    settings = Settings(
        tts_provider="mock",
        tts_fallback_providers="deepgram,groq",
    )
    provider = ProviderRegistry(settings).text_to_speech()
    assert provider.name == "mock"


def test_chain_never_repeats_a_provider():
    settings = Settings(tts_provider="mock", tts_fallback_providers="mock, mock")
    assert Settings.tts_chain.fget(settings) == ["mock"]
