import logging
from typing import Any

import httpx

from app.config import Settings
from app.core.errors import (
    ConfigError,
    ProviderBadResponseError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


class DeepgramClient:
    """Thin httpx wrapper around Deepgram's REST API.

    Mirrors the Groq client's contract: provider status codes and transport
    failures become application errors, so nothing Deepgram-shaped escapes
    this module.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.deepgram_api_key:
            raise ConfigError(
                "DEEPGRAM_API_KEY is not set. Add it to .env, or choose a "
                "different TTS_PROVIDER."
            )
        self._client = httpx.AsyncClient(
            base_url=settings.deepgram_base_url.rstrip("/"),
            headers={"Authorization": f"Token {settings.deepgram_api_key}"},
            timeout=httpx.Timeout(
                connect=settings.provider_connect_timeout,
                read=settings.provider_read_timeout,
                write=settings.provider_read_timeout,
                pool=settings.provider_connect_timeout,
            ),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def post(
        self, path: str, *, params: dict[str, Any], json: dict[str, Any]
    ) -> httpx.Response:
        try:
            response = await self._client.post(path, params=params, json=json)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(details=str(exc)) from exc
        except httpx.HTTPError as exc:
            logger.warning("Deepgram transport failure on %s: %s", path, exc)
            raise ProviderUnavailableError(details=str(exc)) from exc

        if response.status_code >= 400:
            raise self._map_error(response)
        return response

    def _map_error(self, response: httpx.Response) -> Exception:
        detail = self._extract_message(response)
        logger.warning("Deepgram returned %s: %s", response.status_code, detail)

        if response.status_code in (401, 403):
            return ConfigError(
                "The Deepgram API key was rejected. Check DEEPGRAM_API_KEY in .env."
            )
        if response.status_code == 402:
            return ConfigError(
                "The Deepgram account has no remaining credit. "
                f"The provider said: {detail}"
            )
        if response.status_code == 404:
            return ConfigError(
                "Deepgram did not recognize the request, which usually means "
                "DEEPGRAM_TTS_MODEL names a voice that does not exist. "
                "Valid voices are listed at "
                "https://developers.deepgram.com/docs/tts-models"
            )
        if response.status_code == 429:
            return ProviderRateLimitedError(
                retry_after_seconds=self._retry_after_seconds(response),
            )
        if response.status_code >= 500:
            return ProviderUnavailableError()
        return ProviderBadResponseError(details=detail)

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> int | None:
        header = response.headers.get("retry-after")
        if header is None:
            return None
        try:
            return max(0, int(float(header)))
        except ValueError:
            return None

    @staticmethod
    def _extract_message(response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text[:500]
        if isinstance(body, dict):
            for key in ("err_msg", "message", "reason", "error"):
                if key in body:
                    return str(body[key])[:500]
        return str(body)[:500]
