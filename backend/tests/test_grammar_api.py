"""The grammar analysis endpoints, end to end over the API."""


async def say(client, session_id, text):
    response = await client.post(
        f"/api/v1/sessions/{session_id}/turns/text", json={"text": text}
    )
    assert response.status_code == 200
    return response.json()


async def conversation_with_mistakes(client) -> str:
    session_id = (await client.post("/api/v1/sessions")).json()["id"]
    await say(client, session_id, "I go to college yesterday.")
    await say(client, session_id, "The teacher explained the lesson very good.")
    await client.post(f"/api/v1/sessions/{session_id}/end")
    return session_id


async def test_running_analysis_returns_structured_issues(client):
    session_id = await conversation_with_mistakes(client)

    body = (await client.post(
        f"/api/v1/sessions/{session_id}/analysis/grammar"
    )).json()

    assert body["session_id"] == session_id
    assert body["provider"] == "mock"
    assert 0 <= body["grammar_score"] <= 100
    assert body["issue_count"] >= 2

    issue = body["issues"][0]
    assert set(issue) >= {
        "original", "corrected", "explanation", "category", "confidence", "turn_id",
    }


async def test_the_detected_mistakes_are_the_real_ones(client):
    session_id = await conversation_with_mistakes(client)
    body = (await client.post(
        f"/api/v1/sessions/{session_id}/analysis/grammar"
    )).json()

    corrections = {i["corrected"] for i in body["issues"]}
    assert "I went to college yesterday." in corrections
    assert "The teacher explained the lesson very well." in corrections


async def test_analysis_is_stored_and_can_be_fetched_again(client):
    session_id = await conversation_with_mistakes(client)
    created = (await client.post(
        f"/api/v1/sessions/{session_id}/analysis/grammar"
    )).json()

    fetched = (await client.get(
        f"/api/v1/sessions/{session_id}/analysis/grammar"
    )).json()

    assert fetched["grammar_score"] == created["grammar_score"]
    assert fetched["issue_count"] == created["issue_count"]


async def test_fetching_before_running_returns_analysis_not_found(client, session_id):
    response = await client.get(f"/api/v1/sessions/{session_id}/analysis/grammar")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"


async def test_analysing_an_unknown_session_returns_session_not_found(client):
    response = await client.post("/api/v1/sessions/nope/analysis/grammar")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


async def test_rerunning_analysis_replaces_rather_than_duplicates(client):
    session_id = await conversation_with_mistakes(client)
    first = (await client.post(
        f"/api/v1/sessions/{session_id}/analysis/grammar"
    )).json()
    await client.post(f"/api/v1/sessions/{session_id}/analysis/grammar")

    fetched = (await client.get(
        f"/api/v1/sessions/{session_id}/analysis/grammar"
    )).json()

    assert fetched["issue_count"] == first["issue_count"]


async def test_the_transcript_is_unchanged_by_analysis(client):
    """The user's own words must survive analysis untouched."""
    session_id = await conversation_with_mistakes(client)
    before = (await client.get(
        f"/api/v1/sessions/{session_id}/transcript"
    )).json()

    await client.post(f"/api/v1/sessions/{session_id}/analysis/grammar")

    after = (await client.get(f"/api/v1/sessions/{session_id}/transcript")).json()
    assert before["entries"] == after["entries"]
    assert after["entries"][0]["text"] == "I go to college yesterday."


async def test_a_clean_conversation_scores_a_hundred(client):
    session_id = (await client.post("/api/v1/sessions")).json()["id"]
    await say(client, session_id, "I went to college and enjoyed the lesson.")

    body = (await client.post(
        f"/api/v1/sessions/{session_id}/analysis/grammar"
    )).json()

    assert body["grammar_score"] == 100
    assert body["issues"] == []


async def test_analysis_can_run_before_the_session_is_ended(client, session_id):
    """Useful while developing; the feature is aimed at finished conversations."""
    await say(client, session_id, "I go to college yesterday.")

    response = await client.post(f"/api/v1/sessions/{session_id}/analysis/grammar")

    assert response.status_code == 200
    assert response.json()["issue_count"] >= 1
