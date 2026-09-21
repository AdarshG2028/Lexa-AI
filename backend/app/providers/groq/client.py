import logging
from typing import Any

import httpx

from app.config import Settings
from app.core.errors import (
    ConfigError,
    ProviderBadResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


class GroqClient:
    """Thin httpx wrapper around Groq's OpenAI-compatible REST API.

    Everything provider-specific stops here: HTTP status codes, Groq error
    payloads and transport failures are translated into application errors so
    no adapter above this layer ever sees an httpx object.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.groq_api_key:
            raise ConfigError(
                "GROQ_API_KEY is not set. Add it to .env, or set "
                "STT_PROVIDER/LLM_PROVIDER/TTS_PROVIDER to 'mock' to run offline."
            )
        self._settings = settings
        self._timeout = httpx.Timeout(
            connect=settings.provider_connect_timeout,
            read=settings.provider_read_timeout,
            write=settings.provider_read_timeout,
            pool=settings.provider_connect_timeout,
        )
        self._client = httpx.AsyncClient(
            base_url=settings.groq_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            timeout=self._timeout,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> httpx.Response:
        try:
            response = await self._client.post(path, json=json, data=data, files=files)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(details=str(exc)) from exc
        except httpx.HTTPError as exc:
            logger.warning("Groq transport failure on %s: %s", path, exc)
            raise ProviderUnavailableError(details=str(exc)) from exc

        if response.status_code >= 400:
            raise self._map_error(response)
        return response

    async def get(self, path: str) -> httpx.Response:
        try:
            response = await self._client.get(path)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(details=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(details=str(exc)) from exc

        if response.status_code >= 400:
            raise self._map_error(response)
        return response

    async def list_model_ids(self) -> set[str]:
        response = await self.get("/models")
        try:
            return {m["id"] for m in response.json()["data"]}
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderBadResponseError(
                "The model list response could not be parsed."
            ) from exc

    def _map_error(self, response: httpx.Response) -> Exception:
        detail = self._extract_message(response)
        logger.warning("Groq returned %s: %s", response.status_code, detail)

        if response.status_code in (401, 403):
            return ConfigError(
                "The Groq API key was rejected. Check GROQ_API_KEY in .env."
            )
        if response.status_code == 404:
            return ConfigError(
                "Groq rejected the request as not found, which usually means a "
                "model ID in .env no longer exists. List valid IDs with: "
                "curl -H 'Authorization: Bearer $GROQ_API_KEY' "
                f"{self._settings.groq_base_url}/models"
            )
        if response.status_code == 400 and self._is_model_access_issue(detail):
            return ConfigError(
                "The configured model is not usable with this API key yet. "
                f"The provider said: {detail}"
            )
        if response.status_code == 429:
            return ProviderUnavailableError(
                "The AI provider is rate limiting requests. Try again shortly."
            )
        if response.status_code >= 500:
            return ProviderUnavailableError()
        return ProviderBadResponseError(details=detail)

    @staticmethod
    def _is_model_access_issue(detail: str) -> bool:
        """A 400 can mean a bad request or an account-level model restriction.
        The latter is a configuration problem the operator can actually fix, so
        it is surfaced as CONFIG_ERROR with the provider's own instructions."""
        lowered = detail.lower()
        return any(
            phrase in lowered
            for phrase in (
                "terms acceptance",
                "accept the terms",
                "does not exist",
                "do not have access",
                "not authorized to use",
            )
        )

    @staticmethod
    def _extract_message(response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text[:500]
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                return str(error.get("message", body))[:500]
        return str(body)[:500]
