"""Groq adapters are tested against a mocked transport, never the real API.

What matters here is the boundary contract: provider JSON becomes application
models, and provider failures become application errors.
"""

import json

import httpx
import pytest
import respx

from app.config import Settings
from app.core.errors import (
    ConfigError,
    ProviderBadResponseError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.models import ChatMessage
from app.providers.groq.client import GroqClient
from app.providers.groq.llm import GroqLLMProvider
from app.providers.groq.stt import GroqSpeechToTextProvider
from app.providers.groq.tts import GroqTextToSpeechProvider

BASE_URL = "https://api.groq.com/openai/v1"


@pytest.fixture
def groq_settings() -> Settings:
    return Settings(
        stt_provider="groq",
        llm_provider="groq",
        tts_provider="groq",
        groq_api_key="test-key",
        groq_base_url=BASE_URL,
    )


@pytest.fixture
async def client(groq_settings):
    c = GroqClient(groq_settings)
    yield c
    await c.close()


def test_missing_api_key_is_a_config_error():
    with pytest.raises(ConfigError, match="GROQ_API_KEY"):
        GroqClient(Settings(groq_api_key=""))


@respx.mock
async def test_stt_maps_response_to_transcription(client, groq_settings):
    respx.post(f"{BASE_URL}/audio/transcriptions").mock(
        return_value=httpx.Response(
            200,
            json={"text": "  Hello there.  ", "language": "en", "duration": 2.5},
        )
    )
    provider = GroqSpeechToTextProvider(client, groq_settings)
    result = await provider.transcribe(b"fake-wav", "a.wav", "audio/wav")

    assert result.text == "Hello there."
    assert result.language == "en"
    assert result.duration_seconds == 2.5


@respx.mock
async def test_stt_rejects_a_response_missing_text(client, groq_settings):
    respx.post(f"{BASE_URL}/audio/transcriptions").mock(
        return_value=httpx.Response(200, json={"unexpected": "shape"})
    )
    provider = GroqSpeechToTextProvider(client, groq_settings)

    with pytest.raises(ProviderBadResponseError):
        await provider.transcribe(b"fake-wav", "a.wav", "audio/wav")


@respx.mock
async def test_llm_maps_response_to_chat_reply(client, groq_settings):
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "llama-3.3-70b-versatile",
                "choices": [{"message": {"content": "Nice! What happened next?"}}],
            },
        )
    )
    provider = GroqLLMProvider(client, groq_settings)
    reply = await provider.reply([ChatMessage(role="user", content="Hi")])

    assert reply.text == "Nice! What happened next?"
    assert reply.model == "llama-3.3-70b-versatile"


@respx.mock
async def test_the_default_reasoning_model_gets_reasoning_effort_low(client, groq_settings):
    """gpt-oss spends part of max_tokens on hidden "thinking" before any
    visible reply; without this, a request that invites more thought (e.g.
    "give me a recipe") can exhaust the whole budget on reasoning and return
    no visible text at all - which is exactly what an empty reply looks like
    from the caller's side."""
    route = respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "Sounds fun!"}}]}
        )
    )
    provider = GroqLLMProvider(client, groq_settings)
    await provider.reply([ChatMessage(role="user", content="Hi")])

    sent = json.loads(route.calls.last.request.content)
    assert sent["reasoning_effort"] == "low"
    assert sent["max_tokens"] == groq_settings.groq_llm_max_tokens


@respx.mock
async def test_a_non_reasoning_model_is_not_sent_reasoning_effort(client, groq_settings):
    """Groq returns 400 for reasoning_effort on a model that does not support
    it, so switching GROQ_LLM_MODEL away from gpt-oss must not send it."""
    other = groq_settings.model_copy(update={"groq_llm_model": "llama-3.3-70b-versatile"})
    route = respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "Sounds fun!"}}]}
        )
    )
    provider = GroqLLMProvider(client, other)
    await provider.reply([ChatMessage(role="user", content="Hi")])

    sent = json.loads(route.calls.last.request.content)
    assert "reasoning_effort" not in sent


@respx.mock
async def test_llm_rejects_an_empty_reply(client, groq_settings):
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "  "}}]})
    )
    provider = GroqLLMProvider(client, groq_settings)

    with pytest.raises(ProviderBadResponseError):
        await provider.reply([ChatMessage(role="user", content="Hi")])


@respx.mock
async def test_tts_returns_audio_and_stamps_the_provider(client, groq_settings):
    from tests.conftest import make_wav

    body = make_wav(seconds=0.25)
    respx.post(f"{BASE_URL}/audio/speech").mock(
        return_value=httpx.Response(200, content=body)
    )
    provider = GroqTextToSpeechProvider(client, groq_settings)
    speech = await provider.synthesize("Hello")

    assert speech.audio == body
    assert speech.format == "wav"
    assert speech.provider == "groq"


@respx.mock
async def test_tts_rejects_an_empty_body(client, groq_settings):
    respx.post(f"{BASE_URL}/audio/speech").mock(
        return_value=httpx.Response(200, content=b"")
    )
    provider = GroqTextToSpeechProvider(client, groq_settings)

    with pytest.raises(ProviderBadResponseError):
        await provider.synthesize("Hello")


@respx.mock
async def test_rejected_key_becomes_config_error(client, groq_settings):
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(401, json={"error": {"message": "Invalid API Key"}})
    )
    provider = GroqLLMProvider(client, groq_settings)

    with pytest.raises(ConfigError, match="GROQ_API_KEY"):
        await provider.reply([ChatMessage(role="user", content="Hi")])


@respx.mock
async def test_retired_model_id_becomes_config_error_naming_the_fix(client, groq_settings):
    respx.post(f"{BASE_URL}/audio/speech").mock(
        return_value=httpx.Response(404, json={"error": {"message": "model not found"}})
    )
    provider = GroqTextToSpeechProvider(client, groq_settings)

    with pytest.raises(ConfigError, match="model ID"):
        await provider.synthesize("Hello")


@respx.mock
async def test_rate_limit_becomes_a_distinct_retryable_error(client, groq_settings):
    """Distinct from a generic failure, so the frontend can tell a learner to
    wait and try again rather than reporting the app as broken."""
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(429, json={"error": {"message": "slow down"}})
    )
    provider = GroqLLMProvider(client, groq_settings)

    with pytest.raises(ProviderRateLimitedError) as excinfo:
        await provider.reply([ChatMessage(role="user", content="Hi")])
    assert excinfo.value.details["retry_after_seconds"] is None


@respx.mock
async def test_rate_limit_carries_the_providers_retry_after_seconds(client, groq_settings):
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(
            429,
            json={"error": {"message": "slow down"}},
            headers={"Retry-After": "12"},
        )
    )
    provider = GroqLLMProvider(client, groq_settings)

    with pytest.raises(ProviderRateLimitedError) as excinfo:
        await provider.reply([ChatMessage(role="user", content="Hi")])
    assert excinfo.value.details["retry_after_seconds"] == 12


@respx.mock
async def test_a_non_numeric_retry_after_is_treated_as_unknown(client, groq_settings):
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(
            429,
            json={"error": {"message": "slow down"}},
            headers={"Retry-After": "Wed, 23 Sep 2026 06:00:00 GMT"},
        )
    )
    provider = GroqLLMProvider(client, groq_settings)

    with pytest.raises(ProviderRateLimitedError) as excinfo:
        await provider.reply([ChatMessage(role="user", content="Hi")])
    assert excinfo.value.details["retry_after_seconds"] is None


@respx.mock
async def test_server_error_becomes_provider_unavailable(client, groq_settings):
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(503, text="upstream down")
    )
    provider = GroqLLMProvider(client, groq_settings)

    with pytest.raises(ProviderUnavailableError):
        await provider.reply([ChatMessage(role="user", content="Hi")])


@respx.mock
async def test_timeout_becomes_provider_timeout(client, groq_settings):
    respx.post(f"{BASE_URL}/chat/completions").mock(
        side_effect=httpx.ReadTimeout("too slow")
    )
    provider = GroqLLMProvider(client, groq_settings)

    with pytest.raises(ProviderTimeoutError):
        await provider.reply([ChatMessage(role="user", content="Hi")])


def test_registry_selects_implementations_from_config(groq_settings):
    from app.providers.registry import ProviderRegistry

    groq_registry = ProviderRegistry(groq_settings)
    assert groq_registry.speech_to_text().name == "groq"
    assert groq_registry.llm().name == "groq"
    assert groq_registry.text_to_speech().name == "groq"

    mock_registry = ProviderRegistry(
        Settings(stt_provider="mock", llm_provider="mock", tts_provider="mock")
    )
    assert mock_registry.speech_to_text().name == "mock"
    assert mock_registry.llm().name == "mock"
    assert mock_registry.text_to_speech().name == "mock"


@respx.mock
async def test_check_confirms_a_configured_model_exists(client, groq_settings):
    respx.get(f"{BASE_URL}/models").mock(
        return_value=httpx.Response(
            200, json={"data": [{"id": "whisper-large-v3-turbo"}, {"id": "other"}]}
        )
    )
    result = await GroqSpeechToTextProvider(client, groq_settings).check()

    assert result.model == "whisper-large-v3-turbo"
    assert result.model_listed is True
    assert result.note is None


@respx.mock
async def test_check_flags_a_model_id_the_provider_no_longer_lists(client, groq_settings):
    """A retired TTS model ID is the failure this preflight exists to catch."""
    respx.get(f"{BASE_URL}/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "some-other-model"}]})
    )
    result = await GroqTextToSpeechProvider(client, groq_settings).check()

    assert result.model_listed is False
    assert "retired" in result.note


@respx.mock
async def test_terms_acceptance_becomes_actionable_config_error(client, groq_settings):
    """Groq returns 400 for a model the account has not accepted terms for.
    That is fixable configuration, so the provider's instructions are kept."""
    respx.post(f"{BASE_URL}/audio/speech").mock(
        return_value=httpx.Response(
            400,
            json={"error": {"message": "The model `x` requires terms acceptance. "
                                       "Please have the org admin accept the terms at "
                                       "https://console.groq.com/playground"}},
        )
    )
    provider = GroqTextToSpeechProvider(client, groq_settings)

    with pytest.raises(ConfigError, match="terms acceptance"):
        await provider.synthesize("Hello")
