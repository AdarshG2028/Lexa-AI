from app.models import ChatMessage, Session


def build_messages(
    session: Session,
    current_message: str,
    *,
    system_prompt: str,
    max_turns: int,
    max_chars: int,
) -> list[ChatMessage]:
    """Turn a session's stored turns into the message list sent to the LLM.

    A 5-8 minute conversation can run to dozens of exchanges, which would grow
    both cost and latency on every turn. Two limits keep that bounded: only the
    most recent `max_turns` exchanges are considered, and the oldest of those
    are dropped until the history fits within `max_chars`.

    Trimming always removes a complete exchange, never half of one, so the
    model never sees a reply whose question is missing.
    """
    history: list[ChatMessage] = []
    recent = session.turns[-max_turns:] if max_turns > 0 else []

    for turn in recent:
        history.append(ChatMessage(role="user", content=turn.transcript))
        if turn.assistant_response:
            history.append(
                ChatMessage(role="assistant", content=turn.assistant_response)
            )

    while history and _total_chars(history) > max_chars:
        del history[0]
        if history and history[0].role == "assistant":
            del history[0]

    return [
        ChatMessage(role="system", content=system_prompt),
        *history,
        ChatMessage(role="user", content=current_message),
    ]


def _total_chars(messages: list[ChatMessage]) -> int:
    return sum(len(message.content) for message in messages)
