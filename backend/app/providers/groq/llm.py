from app.config import Settings
from app.core.errors import ProviderBadResponseError
from app.models import ChatMessage, ChatReply, ProviderCheck
from app.providers.groq.client import GroqClient

# Groq rejects `reasoning_effort` outright (400) on a model that does not
# support it, so it is only ever sent to models known to accept it - the
# gpt-oss family being the one this app defaults to and was built against.
_REASONING_MODEL_PREFIXES = ("openai/gpt-oss",)


def _supports_reasoning_effort(model: str) -> bool:
    return model.startswith(_REASONING_MODEL_PREFIXES)


class GroqLLMProvider:
    name = "groq"

    def __init__(self, client: GroqClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.groq_llm_model
        self._max_tokens = settings.groq_llm_max_tokens

    async def reply(self, messages: list[ChatMessage]) -> ChatReply:
        payload: dict = {
            "model": self._model,
            "messages": [m.model_dump() for m in messages],
            "temperature": 0.8,
            "max_tokens": self._max_tokens,
        }
        if _supports_reasoning_effort(self._model):
            # A reasoning model spends part of max_tokens on hidden "thinking"
            # before any visible reply. This app wants a quick conversational
            # answer, not deliberation, so reasoning is kept minimal and the
            # budget goes to the reply itself - without this, a request that
            # invites more thought (e.g. "give me a recipe") could exhaust the
            # whole token budget on reasoning and return no visible text at all.
            payload["reasoning_effort"] = "low"

        response = await self._client.post("/chat/completions", json=payload)
        try:
            body = response.json()
            text = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderBadResponseError(
                "The chat response was missing expected fields."
            ) from exc

        if not text or not text.strip():
            raise ProviderBadResponseError("The model returned an empty reply.")
        return ChatReply(text=text.strip(), model=body.get("model"))

    async def check(self) -> ProviderCheck:
        listed = await self._client.list_model_ids()
        found = self._model in listed
        return ProviderCheck(
            provider=self.name,
            model=self._model,
            model_listed=found,
            note=None if found else (
                "This model ID was not in the provider's model list. It may "
                "have been retired or may not be enabled for this API key."
            ),
        )
