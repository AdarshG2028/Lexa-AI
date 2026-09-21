"""Sessions must accept turns only while they are genuinely live, and must
stay readable afterwards so the transcript can be analysed."""

from datetime import datetime, timedelta, timezone

import pytest

from app.api.deps import get_session_repository


async def add_turn(client, session_id, text="hello"):
    return await client.post(
        f"/api/v1/sessions/{session_id}/turns/text", json={"text": text}
    )


async def test_a_new_session_starts_active_and_empty(client):
    body = (await client.post("/api/v1/sessions")).json()

    assert body["status"] == "active"
    assert body["turn_count"] == 0
    assert body["duration_seconds"] >= 0
    assert body["ended_at"] is None


async def test_session_reports_turn_count_and_duration(client, session_id):
    await add_turn(client, session_id, "first")
    await add_turn(client, session_id, "second")

    body = (await client.get(f"/api/v1/sessions/{session_id}")).json()
    assert body["turn_count"] == 2
    assert body["duration_seconds"] > 0


async def test_ending_a_session_marks_it_completed(client, session_id):
    body = (await client.post(f"/api/v1/sessions/{session_id}/end")).json()

    assert body["status"] == "completed"
    assert body["ended_at"] is not None


async def test_ending_a_session_twice_is_not_an_error(client, session_id):
    first = (await client.post(f"/api/v1/sessions/{session_id}/end")).json()
    second = await client.post(f"/api/v1/sessions/{session_id}/end")

    assert second.status_code == 200
    assert second.json()["ended_at"] == first["ended_at"]


async def test_a_completed_session_refuses_new_turns(client, session_id):
    await client.post(f"/api/v1/sessions/{session_id}/end")
    response = await add_turn(client, session_id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SESSION_NOT_ACTIVE"


async def test_a_completed_session_is_still_readable(client, session_id):
    """The transcript is the input to every analysis phase, so ending a
    conversation must not make it inaccessible."""
    await add_turn(client, session_id, "something worth analysing")
    await client.post(f"/api/v1/sessions/{session_id}/end")

    body = (await client.get(f"/api/v1/sessions/{session_id}")).json()
    assert body["status"] == "completed"
    assert body["turns"][0]["transcript"] == "something worth analysing"


async def test_an_idle_session_expires_and_refuses_turns(client, app, session_id):
    repository = app.dependency_overrides[get_session_repository]()
    session = await repository.get(session_id)
    session.last_activity_at = datetime.now(timezone.utc) - timedelta(hours=2)
    await repository.save(session)

    response = await add_turn(client, session_id)

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"


async def test_expiry_is_recorded_on_the_session(client, app, session_id):
    repository = app.dependency_overrides[get_session_repository]()
    session = await repository.get(session_id)
    session.last_activity_at = datetime.now(timezone.utc) - timedelta(hours=2)
    await repository.save(session)

    await add_turn(client, session_id)

    body = (await client.get(f"/api/v1/sessions/{session_id}")).json()
    assert body["status"] == "expired"
    assert body["ended_at"] is not None


async def test_activity_keeps_a_session_alive(client, app, session_id):
    """Idleness is measured from the last turn, not from session start."""
    await add_turn(client, session_id, "first")

    repository = app.dependency_overrides[get_session_repository]()
    session = await repository.get(session_id)
    session.started_at = datetime.now(timezone.utc) - timedelta(hours=5)
    await repository.save(session)

    assert (await add_turn(client, session_id, "second")).status_code == 200


async def test_unknown_session_still_reports_not_found(client):
    response = await add_turn(client, "no-such-session")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"
