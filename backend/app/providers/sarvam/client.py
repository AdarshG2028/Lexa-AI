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


class SarvamClient:
    """Thin httpx wrapper around Sarvam's REST API.

    Mirrors the Groq and Deepgram clients: provider status codes and transport
    failures become application errors here, so no Sarvam-shaped payload ever
    reaches a provider adapter.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.sarvam_api_key:
            raise ConfigError(
                "SARVAM_API_KEY is not set. Add it to .env, or remove the "
                "language from SARVAM_STT_LANGUAGES to keep using the default "
                "speech-to-text provider for it."
            )
        self._client = httpx.AsyncClient(
            base_url=settings.sarvam_base_url.rstrip("/"),
            # Sarvam authenticates with this header, not a bearer token.
            headers={"api-subscription-key": settings.sarvam_api_key},
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
        self,
        path: str,
        *,
        data: dict[str, Any],
        files: dict[str, Any],
    ) -> httpx.Response:
        try:
            response = await self._client.post(path, data=data, files=files)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(details=str(exc)) from exc
        except httpx.HTTPError as exc:
            logger.warning("Sarvam transport failure on %s: %s", path, exc)
            raise ProviderUnavailableError(details=str(exc)) from exc

        if response.status_code >= 400:
            raise self._map_error(response)
        return response

    def _map_error(self, response: httpx.Response) -> Exception:
        detail = self._extract_message(response)
        logger.warning("Sarvam returned %s: %s", response.status_code, detail)

        if response.status_code in (401, 403):
            return ConfigError(
                "The Sarvam API key was rejected. Check SARVAM_API_KEY in .env."
            )
        if response.status_code == 402:
            return ConfigError(
                "The Sarvam account has no remaining credit. "
                f"The provider said: {detail}"
            )
        if response.status_code in (400, 404, 422):
            # The request body is fixed by this adapter, so a rejection here is
            # almost always a bad model ID or language code - something the
            # operator can fix - rather than the learner's audio.
            return ConfigError(
                "Sarvam rejected the transcription request, which usually "
                "means SARVAM_STT_MODEL or the language code is not enabled "
                f"for this key. The provider said: {detail}"
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
            error = body.get("error")
            if isinstance(error, dict):
                return str(error.get("message", body))[:500]
            for key in ("message", "detail", "reason"):
                if key in body:
                    return str(body[key])[:500]
        return str(body)[:500]
