import io
import math
import wave

import pytest
from httpx import ASGITransport, AsyncClient

from app.analysis.memory import InMemoryAnalysisRepository
from app.api.deps import (
    get_analysis_repository,
    get_audio_storage,
    get_registry,
    get_session_repository,
)
from app.config import Settings, get_settings
from app.main import create_app
from app.providers.registry import ProviderRegistry
from app.sessions.memory import InMemorySessionRepository
from app.storage.local import LocalAudioStorage


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch):
    """Tests must never read the developer's .env or shell environment,
    otherwise results depend on whichever keys happen to be configured."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in (
        "STT_PROVIDER", "LLM_PROVIDER", "TTS_PROVIDER", "TTS_FALLBACK_PROVIDERS",
        "GROQ_API_KEY", "DEEPGRAM_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    # Off unless a test is about limiting, so no test can trip a limit by accident.
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        stt_provider="mock",
        llm_provider="mock",
        tts_provider="mock",
        grammar_provider="mock",
        vocabulary_provider="mock",
        pronunciation_provider="mock",
        storage_local_path=str(tmp_path / "audio"),
        max_upload_bytes=5_000_000,
        max_audio_seconds=60,
    )


@pytest.fixture
def app(settings):
    """The app wired to mock providers and a temp storage root.

    dependency_overrides is what keeps the suite offline: no test ever builds a
    Groq client or touches the network.
    """
    repository = InMemorySessionRepository()
    analyses = InMemoryAnalysisRepository()
    storage = LocalAudioStorage(settings.storage_local_path)

    application = create_app()
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_registry] = lambda: ProviderRegistry(settings)
    application.dependency_overrides[get_session_repository] = lambda: repository
    application.dependency_overrides[get_audio_storage] = lambda: storage
    application.dependency_overrides[get_analysis_repository] = lambda: analyses
    return application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def session_id(client) -> str:
    response = await client.post("/api/v1/sessions")
    return response.json()["id"]


def make_wav(seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """A real, decodable WAV so ffmpeg has something valid to normalize."""
    frames = bytearray()
    for i in range(int(sample_rate * seconds)):
        value = int(6000 * math.sin(2 * math.pi * 200 * i / sample_rate))
        frames += value.to_bytes(2, "little", signed=True)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(bytes(frames))
    return buffer.getvalue()
