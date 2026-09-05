"""Fluency endpoints, including the case that cannot be scored."""

from tests.conftest import make_wav


async def spoken_session(client) -> str:
    session_id = (await client.post("/api/v1/sessions")).json()["id"]
    for _ in range(2):
        response = await client.post(
            f"/api/v1/sessions/{session_id}/turns",
            files={"file": ("speech.wav", make_wav(2.0), "audio/wav")},
        )
        assert response.status_code == 200
    await client.post(f"/api/v1/sessions/{session_id}/end")
    return session_id


async def test_fluency_analysis_returns_measurements(client):
    session_id = await spoken_session(client)

    body = (await client.post(
        f"/api/v1/sessions/{session_id}/analysis/fluency"
    )).json()

    assert body["session_id"] == session_id
    assert body["timed_words"] > 0
    assert body["analyzed_seconds"] > 0
    assert body["speaking_rate_wpm"] > 0
    assert body["articulation_rate_wpm"] >= body["speaking_rate_wpm"]
    assert 0 <= body["fluency_score"] <= 100


async def test_the_response_carries_every_metric_the_report_needs(client):
    session_id = await spoken_session(client)
    body = (await client.post(
        f"/api/v1/sessions/{session_id}/analysis/fluency"
    )).json()

    assert set(body) >= {
        "speaking_rate_wpm", "articulation_rate_wpm", "pause_count",
        "long_pause_count", "total_pause_seconds", "filler_count",
        "repetition_count", "restart_count", "findings",
    }


async def test_word_timings_are_stored_on_the_turn(client):
    """Fluency runs after the conversation, so the timings must survive."""
    session_id = await spoken_session(client)

    session = (await client.get(f"/api/v1/sessions/{session_id}")).json()
    words = session["turns"][0]["words"]

    assert len(words) > 0
    assert set(words[0]) == {"word", "start", "end"}
    assert words[0]["end"] >= words[0]["start"]


async def test_a_typed_conversation_reports_that_it_cannot_be_scored(client, session_id):
    await client.post(
        f"/api/v1/sessions/{session_id}/turns/text", json={"text": "typed not spoken"}
    )

    body = (await client.post(
        f"/api/v1/sessions/{session_id}/analysis/fluency"
    )).json()

    assert body["fluency_score"] is None
    assert body["timed_words"] == 0
    assert "no spoken audio" in body["note"]


async def test_analysis_is_stored_and_can_be_fetched_again(client):
    session_id = await spoken_session(client)
    created = (await client.post(
        f"/api/v1/sessions/{session_id}/analysis/fluency"
    )).json()

    fetched = (await client.get(
        f"/api/v1/sessions/{session_id}/analysis/fluency"
    )).json()

    assert fetched["fluency_score"] == created["fluency_score"]
    assert fetched["speaking_rate_wpm"] == created["speaking_rate_wpm"]
    assert len(fetched["findings"]) == len(created["findings"])


async def test_fetching_before_running_returns_analysis_not_found(client, session_id):
    response = await client.get(f"/api/v1/sessions/{session_id}/analysis/fluency")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"


async def test_unknown_session_returns_session_not_found(client):
    response = await client.post("/api/v1/sessions/nope/analysis/fluency")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


async def test_all_three_analyses_coexist_on_one_session(client):
    """Each section is written independently; none may clobber another."""
    session_id = await spoken_session(client)

    for kind in ("grammar", "vocabulary", "fluency"):
        assert (await client.post(
            f"/api/v1/sessions/{session_id}/analysis/{kind}"
        )).status_code == 200

    for kind in ("grammar", "vocabulary", "fluency"):
        assert (await client.get(
            f"/api/v1/sessions/{session_id}/analysis/{kind}"
        )).status_code == 200
