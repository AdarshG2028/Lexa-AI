"""The Phase 2 claim: across a multi-turn conversation, the model is shown
what was said earlier."""

import pytest

from app.api.deps import get_registry
from app.models import ChatMessage, ChatReply, ProviderCheck


class RecordingLLM:
    """Captures exactly what the service sent to the model on each turn."""

    name = "recording"

    def __init__(self) -> None:
        self.calls: list[list[ChatMessage]] = []

    async def reply(self, messages: list[ChatMessage]) -> ChatReply:
        self.calls.append(list(messages))
        return ChatReply(text=f"Reply {len(self.calls)}", model="recording")

    async def check(self) -> ProviderCheck:
        return ProviderCheck(provider=self.name)


@pytest.fixture
def recorder(app):
    llm = RecordingLLM()
    registry = app.dependency_overrides[get_registry]()
    registry.llm = lambda: llm
    app.dependency_overrides[get_registry] = lambda: registry
    return llm


async def say(client, session_id, text):
    response = await client.post(
        f"/api/v1/sessions/{session_id}/turns/text", json={"text": text}
    )
    assert response.status_code == 200
    return response.json()


async def test_the_first_turn_carries_no_history(client, session_id, recorder):
    await say(client, session_id, "My name is Adarsh.")

    assert [m.role for m in recorder.calls[0]] == ["system", "user"]


async def test_later_turns_replay_the_whole_conversation(client, session_id, recorder):
    await say(client, session_id, "My name is Adarsh.")
    await say(client, session_id, "I study computer science.")
    await say(client, session_id, "What is my name?")

    third = recorder.calls[2]
    contents = [m.content for m in third]

    assert "My name is Adarsh." in contents
    assert "I study computer science." in contents
    assert contents[-1] == "What is my name?"
    assert [m.role for m in third] == [
        "system", "user", "assistant", "user", "assistant", "user",
    ]


async def test_assistant_replies_are_fed_back_as_context(client, session_id, recorder):
    await say(client, session_id, "one")
    await say(client, session_id, "two")

    assistant = [m.content for m in recorder.calls[1] if m.role == "assistant"]
    assert assistant == ["Reply 1"]


async def test_history_is_capped_by_configuration(
    client, app, session_id, recorder, settings
):
    settings.conversation_history_turns = 2

    for i in range(5):
        await say(client, session_id, f"message {i}")

    spoken = [m.content for m in recorder.calls[-1] if m.role == "user"]
    assert spoken == ["message 2", "message 3", "message 4"]


async def test_the_response_reports_how_much_context_was_sent(client, session_id):
    first = await say(client, session_id, "hello")
    second = await say(client, session_id, "again")

    assert first["history_messages"] == 2
    assert second["history_messages"] == 4


async def test_separate_sessions_do_not_share_context(client, recorder):
    a = (await client.post("/api/v1/sessions")).json()["id"]
    b = (await client.post("/api/v1/sessions")).json()["id"]

    await say(client, a, "secret for A")
    await say(client, b, "hello from B")

    contents = [m.content for m in recorder.calls[-1]]
    assert "secret for A" not in contents


async def test_the_offline_mock_also_demonstrates_memory(client, session_id):
    """The demo must work without an API key, so the mock LLM proves memory."""
    await say(client, session_id, "I live in Kerala.")
    second = await say(client, session_id, "It is raining today.")

    assert "I live in Kerala." in second["reply_text"]
