from tests.conftest import make_wav


async def test_unknown_session_returns_session_not_found(client):
    response = await client.post(
        "/api/v1/sessions/does-not-exist/turns/text", json={"text": "hello"}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


async def test_unknown_turn_audio_returns_turn_not_found(client, session_id):
    response = await client.get(f"/api/v1/sessions/{session_id}/turns/nope/audio")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TURN_NOT_FOUND"


async def test_text_file_renamed_as_wav_is_rejected_not_crashed(client, session_id):
    response = await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        files={"file": ("fake.wav", b"this is plain text, not audio", "audio/wav")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_AUDIO"


async def test_empty_upload_is_rejected(client, session_id):
    response = await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_AUDIO"


async def test_unsupported_extension_is_rejected(client, session_id):
    response = await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        files={"file": ("notes.txt", b"some bytes here", "text/plain")},
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_AUDIO_FORMAT"


async def test_oversized_upload_is_rejected(client, session_id):
    """The test settings cap uploads at 5 MB."""
    response = await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        files={"file": ("big.wav", make_wav(1.0) + b"\x00" * 5_000_000, "audio/wav")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "AUDIO_TOO_LARGE"


async def test_empty_text_turn_is_rejected_by_validation(client, session_id):
    response = await client.post(
        f"/api/v1/sessions/{session_id}/turns/text", json={"text": ""}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_error_responses_never_leak_provider_internals(client):
    body = (
        await client.post(
            "/api/v1/sessions/missing/turns/text", json={"text": "hi"}
        )
    ).json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
