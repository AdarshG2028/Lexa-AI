"""Deepgram adapter tested against a mocked transport, never the real API."""

import httpx
import pytest
import respx

from app.config import Settings
from app.core.errors import (
    ConfigError,
    ProviderBadResponseError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
)
from app.providers.deepgram.client import DeepgramClient
from app.providers.deepgram.tts import DeepgramTextToSpeechProvider

SPEAK_URL = "https://api.deepgram.com/v1/speak"


@pytest.fixture
def dg_settings() -> Settings:
    return Settings(tts_provider="deepgram", deepgram_api_key="test-key")


@pytest.fixture
async def client(dg_settings):
    c = DeepgramClient(dg_settings)
    yield c
    await c.close()


def test_missing_api_key_is_a_config_error():
    with pytest.raises(ConfigError, match="DEEPGRAM_API_KEY"):
        DeepgramClient(Settings(deepgram_api_key=""))


@respx.mock
async def test_synthesize_returns_audio_and_stamps_the_provider(client, dg_settings):
    from tests.conftest import make_wav

    body = make_wav(seconds=0.25)
    route = respx.post(SPEAK_URL).mock(return_value=httpx.Response(200, content=body))
    speech = await DeepgramTextToSpeechProvider(client, dg_settings).synthesize("Hi")

    assert speech.audio == body
    assert speech.format == "wav"
    assert speech.provider == "deepgram"

    request = route.calls.last.request
    assert request.url.params["model"] == "aura-2-thalia-en"
    assert request.url.params["container"] == "wav"
    assert request.headers["authorization"] == "Token test-key"


@respx.mock
async def test_empty_body_is_rejected(client, dg_settings):
    respx.post(SPEAK_URL).mock(return_value=httpx.Response(200, content=b""))

    with pytest.raises(ProviderBadResponseError):
        await DeepgramTextToSpeechProvider(client, dg_settings).synthesize("Hi")


@respx.mock
async def test_rejected_key_becomes_config_error(client, dg_settings):
    respx.post(SPEAK_URL).mock(
        return_value=httpx.Response(401, json={"err_msg": "Invalid credentials"})
    )
    with pytest.raises(ConfigError, match="DEEPGRAM_API_KEY"):
        await DeepgramTextToSpeechProvider(client, dg_settings).synthesize("Hi")


@respx.mock
async def test_exhausted_credit_becomes_an_actionable_config_error(client, dg_settings):
    respx.post(SPEAK_URL).mock(
        return_value=httpx.Response(402, json={"err_msg": "Project has no credit"})
    )
    with pytest.raises(ConfigError, match="no remaining credit"):
        await DeepgramTextToSpeechProvider(client, dg_settings).synthesize("Hi")


@respx.mock
async def test_unknown_voice_becomes_config_error_naming_the_docs(client, dg_settings):
    respx.post(SPEAK_URL).mock(return_value=httpx.Response(404, json={"err_msg": "nope"}))

    with pytest.raises(ConfigError, match="DEEPGRAM_TTS_MODEL"):
        await DeepgramTextToSpeechProvider(client, dg_settings).synthesize("Hi")


@respx.mock
async def test_rate_limit_becomes_a_distinct_retryable_error(client, dg_settings):
    respx.post(SPEAK_URL).mock(return_value=httpx.Response(429, text="slow down"))

    with pytest.raises(ProviderRateLimitedError) as excinfo:
        await DeepgramTextToSpeechProvider(client, dg_settings).synthesize("Hi")
    assert excinfo.value.details["retry_after_seconds"] is None


@respx.mock
async def test_rate_limit_carries_the_providers_retry_after_seconds(client, dg_settings):
    respx.post(SPEAK_URL).mock(
        return_value=httpx.Response(429, text="slow down", headers={"Retry-After": "5"})
    )

    with pytest.raises(ProviderRateLimitedError) as excinfo:
        await DeepgramTextToSpeechProvider(client, dg_settings).synthesize("Hi")
    assert excinfo.value.details["retry_after_seconds"] == 5


@respx.mock
async def test_exhausted_deepgram_falls_back_to_the_next_provider(dg_settings):
    """The scenario the chain exists for: credit runs out mid-conversation."""
    from app.providers.registry import ProviderRegistry

    respx.post(SPEAK_URL).mock(
        return_value=httpx.Response(402, json={"err_msg": "Project has no credit"})
    )
    settings = Settings(
        tts_provider="deepgram",
        tts_fallback_providers="mock",
        deepgram_api_key="test-key",
    )
    registry = ProviderRegistry(settings)
    try:
        speech = await registry.text_to_speech().synthesize("Hello there")
    finally:
        await registry.close()

    assert speech.provider == "mock"
    assert speech.audio


@respx.mock
async def test_streaming_wav_header_is_repaired_at_the_adapter(client, dg_settings):
    """Deepgram streams WAV with placeholder sizes; strict parsers and browser
    seeking need the real byte counts."""
    import io
    import wave

    from tests.conftest import make_wav

    streamed = bytearray(make_wav(seconds=0.5))
    streamed[4:8] = b"\x24\x00\xff\x7f"
    data_at = bytes(streamed).find(b"data")
    streamed[data_at + 4:data_at + 8] = b"\x00\x00\xff\x7f"

    respx.post(SPEAK_URL).mock(return_value=httpx.Response(200, content=bytes(streamed)))
    speech = await DeepgramTextToSpeechProvider(client, dg_settings).synthesize("Hi")

    with wave.open(io.BytesIO(speech.audio), "rb") as handle:
        assert handle.getnframes() == 8000
