from app.config import Settings
from app.core.errors import ProviderBadResponseError
from app.models import ChatMessage, ChatReply, ProviderCheck
from app.providers.groq.client import GroqClient


class GroqLLMProvider:
    name = "groq"

    def __init__(self, client: GroqClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.groq_llm_model

    async def reply(self, messages: list[ChatMessage]) -> ChatReply:
        response = await self._client.post(
            "/chat/completions",
            json={
                "model": self._model,
                "messages": [m.model_dump() for m in messages],
                "temperature": 0.8,
                "max_tokens": 200,
            },
        )
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
