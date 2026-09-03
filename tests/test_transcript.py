"""The transcript is the deliverable of Phase 3 and the input to every
analysis phase that follows."""

from app.conversation.transcript import build_transcript
from app.models import AudioRef, Session, SessionStatus, Speaker, Turn


def session_with(exchanges, with_audio=False) -> Session:
    session = Session()
    for index, (said, replied) in enumerate(exchanges):
        session.turns.append(
            Turn(
                index=index,
                transcript=said,
                assistant_response=replied,
                user_audio=AudioRef(key=f"u{index}.wav", format="wav",
                                    duration_seconds=2.0) if with_audio else None,
                assistant_audio=AudioRef(key=f"a{index}.wav",
                                         format="wav") if with_audio else None,
            )
        )
    return session


def test_each_exchange_becomes_two_entries_in_speaking_order():
    transcript = build_transcript(session_with([("hello", "hi there"),
                                                ("how are you", "good")]))

    assert [e.speaker for e in transcript.entries] == [
        Speaker.USER, Speaker.ASSISTANT, Speaker.USER, Speaker.ASSISTANT,
    ]
    assert [e.text for e in transcript.entries] == [
        "hello", "hi there", "how are you", "good",
    ]
    assert [e.index for e in transcript.entries] == [0, 1, 2, 3]


def test_a_turn_with_no_reply_yields_only_the_user_entry():
    session = Session()
    session.turns.append(Turn(index=0, transcript="unanswered"))
    transcript = build_transcript(session)

    assert len(transcript.entries) == 1
    assert transcript.entries[0].speaker is Speaker.USER


def test_plain_text_is_a_readable_conversation():
    transcript = build_transcript(session_with([("I go to college", "Which one?")]))

    assert transcript.plain_text == "You: I go to college\nAI: Which one?"


def test_audio_urls_point_at_the_right_speaker():
    transcript = build_transcript(session_with([("a", "b")], with_audio=True))
    user, assistant = transcript.entries

    assert user.audio_url.endswith("/audio/user")
    assert assistant.audio_url.endswith("/audio")
    assert user.audio_duration_seconds == 2.0


def test_entries_have_no_audio_url_when_no_audio_was_stored():
    transcript = build_transcript(session_with([("a", "b")], with_audio=False))

    assert all(e.audio_url is None for e in transcript.entries)


def test_an_empty_session_produces_an_empty_transcript():
    transcript = build_transcript(Session())

    assert transcript.entries == []
    assert transcript.plain_text == ""
    assert transcript.turn_count == 0


def test_transcript_carries_session_metadata():
    session = session_with([("a", "b")])
    session.status = SessionStatus.COMPLETED
    transcript = build_transcript(session)

    assert transcript.session_id == session.id
    assert transcript.status is SessionStatus.COMPLETED
    assert transcript.turn_count == 1
    assert transcript.duration_seconds >= 0


# --- through the API ---

async def say(client, session_id, text):
    return await client.post(
        f"/api/v1/sessions/{session_id}/turns/text", json={"text": text}
    )


async def test_transcript_endpoint_returns_the_conversation(client, session_id):
    await say(client, session_id, "I go to college yesterday.")
    await say(client, session_id, "It was very good.")

    body = (await client.get(f"/api/v1/sessions/{session_id}/transcript")).json()

    assert body["turn_count"] == 2
    assert len(body["entries"]) == 4
    assert body["entries"][0]["text"] == "I go to college yesterday."
    assert body["entries"][0]["speaker"] == "user"
    assert body["entries"][1]["speaker"] == "assistant"


async def test_transcript_is_available_after_the_session_ends(client, session_id):
    await say(client, session_id, "something to analyse")
    await client.post(f"/api/v1/sessions/{session_id}/end")

    body = (await client.get(f"/api/v1/sessions/{session_id}/transcript")).json()

    assert body["status"] == "completed"
    assert body["ended_at"] is not None
    assert body["entries"][0]["text"] == "something to analyse"


async def test_transcript_as_plain_text(client, session_id):
    await say(client, session_id, "hello there")

    response = await client.get(
        f"/api/v1/sessions/{session_id}/transcript", params={"format": "text"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text.startswith("You: hello there\nAI: ")


async def test_transcript_of_an_unknown_session_is_not_found(client):
    response = await client.get("/api/v1/sessions/nope/transcript")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"
