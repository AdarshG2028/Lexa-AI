"""History building decides what the model can remember, and what a long
conversation costs on every turn."""

from app.conversation.history import build_messages
from app.models import Session, Turn

PROMPT = "system prompt"


def session_with(exchanges: list[tuple[str, str]]) -> Session:
    session = Session()
    for index, (said, replied) in enumerate(exchanges):
        session.turns.append(
            Turn(index=index, transcript=said, assistant_response=replied)
        )
    return session


def build(session, current="now", max_turns=12, max_chars=8000):
    return build_messages(
        session, current,
        system_prompt=PROMPT, max_turns=max_turns, max_chars=max_chars,
    )


def test_first_turn_is_system_prompt_plus_the_message():
    messages = build(Session(), current="Hello")

    assert [m.role for m in messages] == ["system", "user"]
    assert messages[0].content == PROMPT
    assert messages[1].content == "Hello"


def test_earlier_exchanges_are_replayed_in_order():
    session = session_with([("I like cricket", "Who is your team?"),
                            ("Chennai", "Nice choice!")])
    messages = build(session, current="They won yesterday")

    assert [m.role for m in messages] == [
        "system", "user", "assistant", "user", "assistant", "user",
    ]
    assert messages[1].content == "I like cricket"
    assert messages[-1].content == "They won yesterday"


def test_only_the_most_recent_exchanges_are_kept():
    session = session_with([(f"said {i}", f"replied {i}") for i in range(20)])
    messages = build(session, max_turns=3)

    spoken = [m.content for m in messages if m.role == "user"]
    assert spoken == ["said 17", "said 18", "said 19", "now"]


def test_history_is_dropped_oldest_first_to_fit_the_character_budget():
    session = session_with([("a" * 100, "b" * 100) for _ in range(10)])
    messages = build(session, max_chars=450)

    history = [m for m in messages if m.role in ("user", "assistant")][:-1]
    assert sum(len(m.content) for m in history) <= 450
    assert history


def test_trimming_never_leaves_a_reply_without_its_question():
    session = session_with([("q" * 60, "a" * 60) for _ in range(6)])
    messages = build(session, max_chars=200)

    history = [m for m in messages if m.role in ("user", "assistant")][:-1]
    assert history[0].role == "user"
    for question, answer in zip(history[::2], history[1::2]):
        assert question.role == "user"
        assert answer.role == "assistant"


def test_a_turn_with_no_reply_yet_contributes_only_the_user_message():
    session = Session()
    session.turns.append(Turn(index=0, transcript="orphan", assistant_response=None))
    messages = build(session)

    assert [m.role for m in messages] == ["system", "user", "user"]


def test_zero_history_turns_disables_context_entirely():
    session = session_with([("old", "reply")])
    messages = build(session, max_turns=0)

    assert [m.role for m in messages] == ["system", "user"]


def test_the_current_message_survives_an_impossibly_small_budget():
    session = session_with([("old", "reply")])
    messages = build(session, current="keep me", max_chars=0)

    assert [m.role for m in messages] == ["system", "user"]
    assert messages[-1].content == "keep me"
