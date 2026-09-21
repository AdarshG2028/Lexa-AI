import logging
import math
import time
from collections import defaultdict, deque
from collections.abc import Callable

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import Settings
from app.core.errors import RateLimitedError

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60.0
# Bounds memory when many distinct addresses each make a request and vanish.
MAX_TRACKED_KEYS = 10_000

EXEMPT_PATHS = {"/health"}


class SlidingWindowLimiter:
    """Counts requests per key over a moving window.

    Every request is remembered, so the limit holds across any 60-second span
    rather than resetting on the clock and allowing a double burst at the
    boundary. Held in process memory: one instance shares nothing with another
    and forgets everything on restart, which suits a single small server.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def retry_after(self, key: tuple[str, str], limit: int) -> int:
        """Seconds until a request would be allowed; 0 if it is allowed now."""
        now = self._clock()
        hits = self._hits.get(key)
        if not hits:
            return 0
        self._expire(hits, now)
        if len(hits) < limit:
            return 0
        return max(1, math.ceil(hits[0] + WINDOW_SECONDS - now))

    def record(self, key: tuple[str, str]) -> None:
        if len(self._hits) >= MAX_TRACKED_KEYS:
            self._prune()
        self._hits[key].append(self._clock())

    def _expire(self, hits: deque[float], now: float) -> None:
        while hits and hits[0] <= now - WINDOW_SECONDS:
            hits.popleft()

    def _prune(self) -> None:
        now = self._clock()
        for key in list(self._hits):
            self._expire(self._hits[key], now)
            if not self._hits[key]:
                del self._hits[key]


def classify(method: str, path: str) -> str | None:
    """Which tight bucket a request counts against, if any."""
    if method != "POST":
        return None
    if path.endswith("/turns") or path.endswith("/turns/text"):
        return "turns"
    if "/analysis/" in path:
        return "analysis"
    return None


def client_ip(scope: Scope, trusted_hops: int) -> str:
    """The address the request really came from.

    X-Forwarded-For is a list that each proxy appends to, so the left end is
    whatever the client chose to claim and can be forged. Only entries added by
    proxies we trust can be believed, and those are at the right end.
    """
    peer = (scope.get("client") or ("unknown", 0))[0]
    if trusted_hops <= 0:
        return peer

    header = next(
        (v for k, v in scope["headers"] if k == b"x-forwarded-for"), b""
    ).decode("latin-1")
    parts = [p.strip() for p in header.split(",") if p.strip()]
    if len(parts) < trusted_hops:
        return peer
    return parts[-trusted_hops]


class RateLimitMiddleware:
    """Per-IP request limiting, answering 429 in the API's normal error format.

    Written as plain ASGI middleware and placed inside the CORS middleware, so
    that a 429 still carries CORS headers. Without them the browser hides the
    response and shows a generic network failure instead of the message.
    """

    def __init__(
        self,
        app: ASGIApp,
        settings: Settings,
        limiter: SlidingWindowLimiter | None = None,
    ) -> None:
        self.app = app
        self._limiter = limiter or SlidingWindowLimiter()
        self._hops = settings.trusted_proxy_hops
        self._limits = {
            "general": settings.rate_limit_general_per_minute,
            "turns": settings.rate_limit_turns_per_minute,
            "analysis": settings.rate_limit_analysis_per_minute,
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._exempt(scope):
            await self.app(scope, receive, send)
            return

        ip = client_ip(scope, self._hops)
        buckets = ["general"]
        tight = classify(scope["method"], scope["path"])
        if tight:
            buckets.append(tight)

        wait = 0
        for bucket in buckets:
            limit = self._limits[bucket]
            if limit > 0:
                wait = max(wait, self._limiter.retry_after((ip, bucket), limit))

        if wait:
            # The raw header is logged beside the chosen address so a wrong
            # TRUSTED_PROXY_HOPS is visible: every user showing the same
            # address means the proxy's own address is being counted.
            logger.info(
                "Rate limited %s on %s (retry in %ss); forwarded-for=%r",
                ip, "+".join(buckets), wait,
                dict(scope["headers"]).get(b"x-forwarded-for", b"").decode("latin-1"),
            )
            error = RateLimitedError(
                f"You are sending requests too quickly. Try again in {wait} "
                f"second{'s' if wait != 1 else ''}.",
                retry_after_seconds=wait,
            )
            response = JSONResponse(
                status_code=error.status_code,
                content=error.to_dict(),
                headers={"Retry-After": str(wait)},
            )
            await response(scope, receive, send)
            return

        for bucket in buckets:
            if self._limits[bucket] > 0:
                self._limiter.record((ip, bucket))
        await self.app(scope, receive, send)

    @staticmethod
    def _exempt(scope: Scope) -> bool:
        # Preflights are answered by the CORS middleware before they get here,
        # and the health check is polled by the host every few seconds.
        return scope["method"] == "OPTIONS" or scope["path"] in EXEMPT_PATHS
