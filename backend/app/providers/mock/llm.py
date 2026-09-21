from app.models import ChatMessage, ChatReply, ProviderCheck


class MockLLMProvider:
    """Deterministic offline conversation partner.

    It quotes back the earliest thing the user said as well as the newest, so
    that whether conversation history actually reached the model is visible
    without calling a real LLM.
    """

    name = "mock"

    async def reply(self, messages: list[ChatMessage]) -> ChatReply:
        spoken = [m.content for m in messages if m.role == "user"]
        current = spoken[-1] if spoken else ""
        earlier = spoken[:-1]

        if earlier:
            text = (
                f"Earlier you told me: {earlier[0]} "
                f"Now you say: {current} Tell me more about that."
            )
        else:
            text = f"That's interesting. You said: {current} Tell me more about that."

        return ChatReply(text=text, model="mock-llm")

    async def check(self) -> ProviderCheck:
        return ProviderCheck(provider=self.name)
