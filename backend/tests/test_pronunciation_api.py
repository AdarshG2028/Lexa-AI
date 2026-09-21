"""Pronunciation endpoints, using the offline provider."""

from tests.conftest import make_wav


async def spoken_session(client, turns: int = 1) -> str:
    session_id = (await client.post("/api/v1/sessions")).json()["id"]
    for _ in range(turns):
        response = await client.post(
            f"/api/v1/sessions/{session_id}/turns",
            files={"file": ("speech.wav", make_wav(1.5), "audio/wav")},
        )
        assert response.status_code == 200
    await client.post(f"/api/v1/sessions/{session_id}/end")
    return session_id


async def test_pronunciation_analysis_returns_a_report(client):
    session_id = await spoken_session(client)

    body = (await client.post(
        f"/api/v1/sessions/{session_id}/analysis/pronunciation"
    )).json()

    assert body["session_id"] == session_id
    assert body["provider"] == "mock"
    assert body["words_analyzed"] > 0
    assert set(body) >= {
        "pronunciation_score", "issues", "substitutions_found", "analyzed_seconds",
    }


async def test_a_typed_conversation_cannot_be_analysed(client, session_id):
    """Pronunciation needs audio; a fabricated score would be worse than none."""
    await client.post(
        f"/api/v1/sessions/{session_id}/turns/text", json={"text": "typed only"}
    )

    body = (await client.post(
        f"/api/v1/sessions/{session_id}/analysis/pronunciation"
    )).json()

    assert body["pronunciation_score"] is None
    assert "no spoken audio" in body["note"]
    assert body["issues"] == []


async def test_analysis_is_stored_and_can_be_fetched_again(client):
    session_id = await spoken_session(client)
    created = (await client.post(
        f"/api/v1/sessions/{session_id}/analysis/pronunciation"
    )).json()

    fetched = (await client.get(
        f"/api/v1/sessions/{session_id}/analysis/pronunciation"
    )).json()

    assert fetched["pronunciation_score"] == created["pronunciation_score"]
    assert fetched["issue_count"] == created["issue_count"]


async def test_fetching_before_running_returns_analysis_not_found(client, session_id):
    response = await client.get(
        f"/api/v1/sessions/{session_id}/analysis/pronunciation"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"


async def test_unknown_session_returns_session_not_found(client):
    response = await client.post("/api/v1/sessions/nope/analysis/pronunciation")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


async def test_all_four_analyses_coexist_on_one_session(client):
    session_id = await spoken_session(client)

    for kind in ("grammar", "vocabulary", "fluency", "pronunciation"):
        assert (await client.post(
            f"/api/v1/sessions/{session_id}/analysis/{kind}"
        )).status_code == 200

    for kind in ("grammar", "vocabulary", "fluency", "pronunciation"):
        assert (await client.get(
            f"/api/v1/sessions/{session_id}/analysis/{kind}"
        )).status_code == 200


async def test_the_transcript_is_unchanged_by_analysis(client):
    session_id = await spoken_session(client)
    before = (await client.get(f"/api/v1/sessions/{session_id}/transcript")).json()

    await client.post(f"/api/v1/sessions/{session_id}/analysis/pronunciation")

    after = (await client.get(f"/api/v1/sessions/{session_id}/transcript")).json()
    assert before["entries"] == after["entries"]
