"""Vocabulary endpoints, and the rule that analysis sections are independent."""


async def say(client, session_id, text):
    response = await client.post(
        f"/api/v1/sessions/{session_id}/turns/text", json={"text": text}
    )
    assert response.status_code == 200
    return response.json()


async def repetitive_conversation(client) -> str:
    session_id = (await client.post("/api/v1/sessions")).json()["id"]
    await say(client, session_id, "The food was very good.")
    await say(client, session_id, "The movie was very good.")
    await say(client, session_id, "The trip was very good too.")
    await client.post(f"/api/v1/sessions/{session_id}/end")
    return session_id


async def test_running_vocabulary_analysis_returns_structured_issues(client):
    session_id = await repetitive_conversation(client)

    body = (await client.post(
        f"/api/v1/sessions/{session_id}/analysis/vocabulary"
    )).json()

    assert body["session_id"] == session_id
    assert body["provider"] == "mock"
    assert 0 <= body["vocabulary_score"] <= 100
    assert body["words_analyzed"] > 0
    assert 0 < body["lexical_diversity"] <= 1

    issue = body["issues"][0]
    assert set(issue) >= {
        "type", "text", "occurrences", "example", "suggestions", "explanation",
    }


async def test_the_repeated_phrase_is_found_with_an_exact_count(client):
    session_id = await repetitive_conversation(client)
    body = (await client.post(
        f"/api/v1/sessions/{session_id}/analysis/vocabulary"
    )).json()

    phrase = next(i for i in body["issues"] if i["text"] == "very good")
    assert phrase["occurrences"] == 3
    assert phrase["suggestions"]


async def test_analysis_is_stored_and_can_be_fetched_again(client):
    session_id = await repetitive_conversation(client)
    created = (await client.post(
        f"/api/v1/sessions/{session_id}/analysis/vocabulary"
    )).json()

    fetched = (await client.get(
        f"/api/v1/sessions/{session_id}/analysis/vocabulary"
    )).json()

    assert fetched["vocabulary_score"] == created["vocabulary_score"]
    assert fetched["issue_count"] == created["issue_count"]
    assert fetched["issues"][0]["suggestions"] == created["issues"][0]["suggestions"]


async def test_fetching_before_running_returns_analysis_not_found(client, session_id):
    response = await client.get(f"/api/v1/sessions/{session_id}/analysis/vocabulary")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"


async def test_unknown_session_returns_session_not_found(client):
    response = await client.post("/api/v1/sessions/nope/analysis/vocabulary")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


async def test_grammar_and_vocabulary_do_not_overwrite_each_other(client):
    """Each section is written independently, in either order."""
    session_id = await repetitive_conversation(client)

    await client.post(f"/api/v1/sessions/{session_id}/analysis/grammar")
    await client.post(f"/api/v1/sessions/{session_id}/analysis/vocabulary")

    grammar = await client.get(f"/api/v1/sessions/{session_id}/analysis/grammar")
    vocabulary = await client.get(
        f"/api/v1/sessions/{session_id}/analysis/vocabulary"
    )

    assert grammar.status_code == 200
    assert vocabulary.status_code == 200
    assert grammar.json()["session_id"] == session_id


async def test_the_reverse_order_also_preserves_both(client):
    session_id = await repetitive_conversation(client)

    await client.post(f"/api/v1/sessions/{session_id}/analysis/vocabulary")
    await client.post(f"/api/v1/sessions/{session_id}/analysis/grammar")

    assert (await client.get(
        f"/api/v1/sessions/{session_id}/analysis/vocabulary"
    )).status_code == 200
    assert (await client.get(
        f"/api/v1/sessions/{session_id}/analysis/grammar"
    )).status_code == 200


async def test_the_transcript_is_unchanged_by_analysis(client):
    session_id = await repetitive_conversation(client)
    before = (await client.get(f"/api/v1/sessions/{session_id}/transcript")).json()

    await client.post(f"/api/v1/sessions/{session_id}/analysis/vocabulary")

    after = (await client.get(f"/api/v1/sessions/{session_id}/transcript")).json()
    assert before["entries"] == after["entries"]
