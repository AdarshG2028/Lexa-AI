"""The whole API exercised against the database store, not just the in-memory
one, and across a simulated restart."""

import io
import wave

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_audio_storage, get_registry, get_session_repository
from app.config import get_settings
from app.db.engine import create_engine, create_session_factory, create_tables
from app.main import create_app
from app.providers.registry import ProviderRegistry
from app.sessions.sql import SqlSessionRepository
from app.storage.local import LocalAudioStorage
from tests.conftest import make_wav


@pytest.fixture
async def database_url(tmp_path):
    return f"sqlite+aiosqlite:///{tmp_path / 'api.db'}"


@pytest.fixture
async def sql_client(settings, database_url):
    """A client whose sessions live in SQLite. Providers stay mocked."""
    engine = create_engine(database_url)
    await create_tables(engine)
    repository = SqlSessionRepository(create_session_factory(engine))

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_registry] = lambda: ProviderRegistry(settings)
    app.dependency_overrides[get_session_repository] = lambda: repository
    app.dependency_overrides[get_audio_storage] = lambda: LocalAudioStorage(
        settings.storage_local_path
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    await engine.dispose()


async def say(client, session_id, text):
    response = await client.post(
        f"/api/v1/sessions/{session_id}/turns/text", json={"text": text}
    )
    assert response.status_code == 200
    return response.json()


async def test_a_full_conversation_persists_to_the_database(sql_client):
    session_id = (await sql_client.post("/api/v1/sessions")).json()["id"]
    await say(sql_client, session_id, "My name is Adarsh.")
    await say(sql_client, session_id, "I study computer science.")
    await sql_client.post(f"/api/v1/sessions/{session_id}/end")

    body = (await sql_client.get(f"/api/v1/sessions/{session_id}/transcript")).json()

    assert body["status"] == "completed"
    assert body["turn_count"] == 2
    assert body["entries"][0]["text"] == "My name is Adarsh."
    assert body["entries"][2]["text"] == "I study computer science."


async def test_context_still_works_when_history_comes_from_the_database(sql_client):
    """History is rebuilt from stored rows, so memory must survive the round
    trip through SQLite."""
    session_id = (await sql_client.post("/api/v1/sessions")).json()["id"]
    await say(sql_client, session_id, "I live in Kerala.")
    second = await say(sql_client, session_id, "It is raining.")

    assert second["history_messages"] == 4
    assert "I live in Kerala." in second["reply_text"]


async def test_audio_turn_persists_its_audio_reference(sql_client):
    session_id = (await sql_client.post("/api/v1/sessions")).json()["id"]
    turn = await sql_client.post(
        f"/api/v1/sessions/{session_id}/turns",
        files={"file": ("speech.wav", make_wav(1.0), "audio/wav")},
    )
    assert turn.status_code == 200

    session = (await sql_client.get(f"/api/v1/sessions/{session_id}")).json()
    user_audio = session["turns"][0]["user_audio"]

    assert user_audio["format"] == "wav"
    assert user_audio["duration_seconds"] > 0
    assert user_audio["size_bytes"] > 0


async def test_user_audio_can_be_downloaded_for_later_analysis(sql_client):
    session_id = (await sql_client.post("/api/v1/sessions")).json()["id"]
    turn = (await sql_client.post(
        f"/api/v1/sessions/{session_id}/turns",
        files={"file": ("speech.wav", make_wav(1.0, sample_rate=44100), "audio/wav")},
    )).json()

    response = await sql_client.get(
        f"/api/v1/sessions/{session_id}/turns/{turn['turn_id']}/audio/user"
    )

    assert response.status_code == 200
    with wave.open(io.BytesIO(response.content), "rb") as handle:
        assert handle.getframerate() == 16000
        assert handle.getnchannels() == 1


async def test_a_turn_without_user_audio_has_none_to_download(sql_client):
    session_id = (await sql_client.post("/api/v1/sessions")).json()["id"]
    turn = await say(sql_client, session_id, "typed, not spoken")

    response = await sql_client.get(
        f"/api/v1/sessions/{session_id}/turns/{turn['turn_id']}/audio/user"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TURN_NOT_FOUND"


async def test_the_conversation_survives_a_restart(settings, database_url):
    """Two independent app instances over one database file."""
    async def build_client():
        engine = create_engine(database_url)
        await create_tables(engine)
        repository = SqlSessionRepository(create_session_factory(engine))
        app = create_app()
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_registry] = lambda: ProviderRegistry(settings)
        app.dependency_overrides[get_session_repository] = lambda: repository
        app.dependency_overrides[get_audio_storage] = lambda: LocalAudioStorage(
            settings.storage_local_path
        )
        return app, engine

    app, engine = await build_client()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session_id = (await client.post("/api/v1/sessions")).json()["id"]
        await say(client, session_id, "remember this across the restart")
    await engine.dispose()

    app2, engine2 = await build_client()
    async with AsyncClient(
        transport=ASGITransport(app=app2), base_url="http://test"
    ) as client:
        body = (await client.get(f"/api/v1/sessions/{session_id}/transcript")).json()
    await engine2.dispose()

    assert body["entries"][0]["text"] == "remember this across the restart"
