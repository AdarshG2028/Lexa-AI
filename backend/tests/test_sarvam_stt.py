"""Sarvam speech-to-text for Kannada, Tamil and Telugu.

Sarvam is the second STT vendor in the app. These tests cover the adapter's
HTTP shape, the error translation, and the routing that keeps Hindi and
English on the incumbent provider even when Sarvam is configured.
"""

import httpx
import pytest
import respx

from app.config import Settings
from app.core.errors import ConfigError
from app.models import ProviderCheck, Transcription
from app.providers.registry import ProviderRegistry
from app.providers.routing import LanguageRoutingSpeechToTextProvider
from app.providers.sarvam.client import SarvamClient
from app.providers.sarvam.stt import SarvamSpeechToTextProvider

BASE_URL = "https://api.sarvam.ai"


@pytest.fixture
def sarvam_settings() -> Settings:
    return Settings(
        stt_provider="groq",
        groq_api_key="groq-key",
        sarvam_api_key="sarvam-key",
        sarvam_base_url=BASE_URL,
        sarvam_stt_model="saaras:v4",
    )


@pytest.fixture
async def sarvam_client(sarvam_settings):
    client = SarvamClient(sarvam_settings)
    yield client
    await client.close()


def ok(**body) -> httpx.Response:
    return httpx.Response(200, json=body)


# --- the adapter ----------------------------------------------------------


@respx.mock
async def test_sarvam_transcribes_with_the_language_pinned(
    sarvam_client, sarvam_settings
):
    route = respx.post(f"{BASE_URL}/speech-to-text").mock(
        return_value=ok(
            request_id="r1", transcript="ನಮಸ್ಕಾರ", language_code="kn-IN"
        )
    )
    provider = SarvamSpeechToTextProvider(sarvam_client, sarvam_settings)

    result = await provider.transcribe(b"wav", "a.wav", "audio/wav", language="kn")

    assert result.text == "ನಮಸ್ಕಾರ"
    assert result.language == "kn-IN"
    # Sarvam's REST API has no word-level timings; the field stays empty.
    assert result.words == []

    request = route.calls.last.request
    assert request.headers["api-subscription-key"] == "sarvam-key"
    body = request.content
    assert b'name="language_code"' in body
    assert b"\r\n\r\nkn-IN\r\n" in body
    assert b'name="model"' in body
    assert b"\r\n\r\nsaaras:v4\r\n" in body
    assert b'name="file"' in body


@respx.mock
async def test_each_indic_language_becomes_a_bcp47_code(
    sarvam_client, sarvam_settings
):
    route = respx.post(f"{BASE_URL}/speech-to-text").mock(
        return_value=ok(transcript="ok", language_code="te-IN")
    )
    provider = SarvamSpeechToTextProvider(sarvam_client, sarvam_settings)

    for code, expected in (("hi", "hi-IN"), ("ta", "ta-IN"), ("te", "te-IN")):
        await provider.transcribe(b"wav", "a.wav", "audio/wav", language=code)
        assert expected.encode() in route.calls.last.request.content


@respx.mock
async def test_an_empty_transcript_is_returned_not_invented(
    sarvam_client, sarvam_settings
):
    respx.post(f"{BASE_URL}/speech-to-text").mock(
        return_value=ok(transcript="", language_code="ta-IN")
    )
    provider = SarvamSpeechToTextProvider(sarvam_client, sarvam_settings)

    result = await provider.transcribe(b"wav", "a.wav", "audio/wav", language="ta")

    assert result.text == ""


@respx.mock
async def test_a_rejected_key_is_a_config_error(sarvam_client, sarvam_settings):
    respx.post(f"{BASE_URL}/speech-to-text").mock(
        return_value=httpx.Response(
            403, json={"error": {"message": "invalid api key"}}
        )
    )
    provider = SarvamSpeechToTextProvider(sarvam_client, sarvam_settings)

    with pytest.raises(ConfigError):
        await provider.transcribe(b"wav", "a.wav", "audio/wav", language="kn")


@respx.mock
async def test_a_bad_model_is_reported_as_configuration(
    sarvam_client, sarvam_settings
):
    respx.post(f"{BASE_URL}/speech-to-text").mock(
        return_value=httpx.Response(
            422, json={"error": {"message": "model not supported"}}
        )
    )
    provider = SarvamSpeechToTextProvider(sarvam_client, sarvam_settings)

    with pytest.raises(ConfigError) as caught:
        await provider.transcribe(b"wav", "a.wav", "audio/wav", language="kn")

    assert "SARVAM_STT_MODEL" in caught.value.message


async def test_the_health_check_does_not_claim_a_model_list(
    sarvam_client, sarvam_settings
):
    check = await SarvamSpeechToTextProvider(sarvam_client, sarvam_settings).check()

    # None means "not checked", which the health route treats as healthy
    # rather than degraded.
    assert check.model_listed is None
    assert check.model == "saaras:v4"


# --- routing --------------------------------------------------------------


class FakeSTT:
    def __init__(self, name: str) -> None:
        self.name = name
        self.languages: list[str | None] = []

    async def transcribe(self, audio, filename, mime_type, language=None):
        self.languages.append(language)
        return Transcription(text=self.name, language=language)

    async def check(self) -> ProviderCheck:
        return ProviderCheck(provider=self.name, model_listed=True)


async def test_routing_sends_each_language_to_its_provider():
    default, sarvam = FakeSTT("default"), FakeSTT("sarvam")
    router = LanguageRoutingSpeechToTextProvider(
        default, {"kn": sarvam, "ta": sarvam, "te": sarvam}
    )

    def speak(language):
        return router.transcribe(b"", "a.wav", "audio/wav", language=language)

    assert (await speak("kn")).text == "sarvam"
    assert (await speak("ta")).text == "sarvam"
    assert (await speak("te")).text == "sarvam"
    assert (await speak("hi")).text == "default"
    assert (await speak(None)).text == "default"


async def test_routing_checks_every_provider_it_could_reach():
    default, sarvam = FakeSTT("default"), FakeSTT("sarvam")
    router = LanguageRoutingSpeechToTextProvider(
        default, {"kn": sarvam, "ta": sarvam, "te": sarvam}
    )

    check = await router.check()

    assert check.model_listed is True


# --- registry wiring ------------------------------------------------------


async def test_without_a_key_the_languages_stay_on_the_default_provider():
    settings = Settings(stt_provider="groq", groq_api_key="g", sarvam_api_key="")
    registry = ProviderRegistry(settings)
    try:
        provider = registry.speech_to_text()
        assert provider.name == "groq"
    finally:
        await registry.close()


async def test_a_configured_key_routes_only_the_listed_languages():
    settings = Settings(
        stt_provider="groq",
        groq_api_key="g",
        sarvam_api_key="s",
        sarvam_stt_languages="kn,ta,te",
    )
    registry = ProviderRegistry(settings)
    try:
        provider = registry.speech_to_text()
        assert provider.name == "routing"
        assert provider.provider_for("kn").name == "sarvam"
        assert provider.provider_for("ta").name == "sarvam"
        assert provider.provider_for("te").name == "sarvam"
        # Hindi was measured equal on Whisper and deliberately stays there.
        assert provider.provider_for("hi").name == "groq"
    finally:
        await registry.close()


async def test_the_route_list_is_configurable():
    settings = Settings(
        stt_provider="groq",
        groq_api_key="g",
        sarvam_api_key="s",
        sarvam_stt_languages="kn",
    )
    registry = ProviderRegistry(settings)
    try:
        provider = registry.speech_to_text()
        assert provider.provider_for("kn").name == "sarvam"
        assert provider.provider_for("ta").name == "groq"
    finally:
        await registry.close()


async def test_mock_mode_never_builds_a_network_route():
    settings = Settings(stt_provider="mock", sarvam_api_key="s")
    registry = ProviderRegistry(settings)
    try:
        assert registry.speech_to_text().name == "mock"
    finally:
        await registry.close()


def test_health_reports_the_routes_only_when_they_are_active():
    off = Settings(stt_provider="groq", groq_api_key="g", sarvam_api_key="")
    on = Settings(stt_provider="groq", groq_api_key="g", sarvam_api_key="s")

    assert off.stt_language_routes == {}
    assert on.stt_language_routes == {"kn": "sarvam", "ta": "sarvam", "te": "sarvam"}
