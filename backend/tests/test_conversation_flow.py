import wave
import io

from tests.conftest import make_wav

from app.providers.mock.stt import MOCK_TRANSCRIPT


async def test_start_session(client):
    response = await client.post("/api/v1/sessions")
    assert response.status_code == 201

    body = response.json()
    assert body["status"] == "active"
    assert body["turns"] == []
    assert body["id"]


async def test_audio_turn_returns_transcript_reply_and_audio(client, session_id):
    response = await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        files={"file": ("speech.wav", make_wav(1.0), "audio/wav")},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["transcript"] == MOCK_TRANSCRIPT
    assert body["reply_text"]
    assert body["audio_url"] == (
        f"/api/v1/sessions/{session_id}/turns/{body['turn_id']}/audio"
    )
    assert set(body["timings_ms"]) == {"stt", "llm", "tts", "total"}


async def test_reply_audio_is_a_playable_wav(client, session_id):
    turn = await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        files={"file": ("speech.wav", make_wav(1.0), "audio/wav")},
    )
    audio = await client.get(turn.json()["audio_url"])

    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/wav"

    with wave.open(io.BytesIO(audio.content), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getframerate() == 16000
        assert handle.getnframes() > 0


async def test_text_turn_skips_stt_and_still_returns_audio(client, session_id):
    response = await client.post(
        f"/api/v1/sessions/{session_id}/turns/text",
        json={"text": "I go to college yesterday."},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["transcript"] == "I go to college yesterday."
    assert body["timings_ms"]["stt"] == 0
    assert (await client.get(body["audio_url"])).status_code == 200


async def test_turns_accumulate_on_the_session(client, session_id):
    for text in ("First message.", "Second message."):
        await client.post(
            f"/api/v1/sessions/{session_id}/turns/text", json={"text": text}
        )

    session = (await client.get(f"/api/v1/sessions/{session_id}")).json()
    assert [t["index"] for t in session["turns"]] == [0, 1]
    assert session["turns"][0]["transcript"] == "First message."
    assert session["turns"][1]["assistant_response"]


async def test_user_audio_is_retained_as_16k_mono_wav(client, session_id):
    """Later phases analyse the user's own audio, so it must survive ingest."""
    turn = await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        files={"file": ("speech.wav", make_wav(1.0, sample_rate=44100), "audio/wav")},
    )
    session = (await client.get(f"/api/v1/sessions/{session_id}")).json()

    user_audio = session["turns"][0]["user_audio"]
    assert user_audio["format"] == "wav"
    assert user_audio["duration_seconds"] > 0
    assert user_audio["key"].startswith(f"{session_id}/")
    assert turn.status_code == 200


async def test_end_session_marks_it_completed(client, session_id):
    response = await client.post(f"/api/v1/sessions/{session_id}/end")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "completed"
    assert body["ended_at"] is not None
