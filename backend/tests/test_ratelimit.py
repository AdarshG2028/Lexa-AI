"""Per-IP rate limiting.

The parts most likely to be wrong are the ones that depend on the network in
front of the app - which address counts as the client, and whether a rejection
still reaches the browser - so those are tested through the real middleware
stack rather than only on the limiter class.
"""

import pytest

from app.core.ratelimit import SlidingWindowLimiter, client_ip


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def scope_with(forwarded: str | None, peer: str = "10.0.0.1") -> dict:
    headers = []
    if forwarded is not None:
        headers.append((b"x-forwarded-for", forwarded.encode()))
    return {"client": (peer, 5000), "headers": headers}


# --- the limiter on its own -------------------------------------------------


def test_requests_under_the_limit_are_allowed():
    limiter = SlidingWindowLimiter(FakeClock())
    key = ("1.1.1.1", "turns")

    for _ in range(3):
        assert limiter.retry_after(key, limit=3) == 0
        limiter.record(key)


def test_the_request_over_the_limit_is_refused_with_a_wait_time():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock)
    key = ("1.1.1.1", "turns")
    for _ in range(3):
        limiter.record(key)
        clock.now += 10

    assert limiter.retry_after(key, limit=3) == 30


def test_the_window_slides_rather_than_resetting_on_the_clock():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock)
    key = ("1.1.1.1", "turns")
    limiter.record(key)
    clock.now += 30
    limiter.record(key)

    clock.now += 31
    assert limiter.retry_after(key, limit=2) == 0

    limiter.record(key)
    assert limiter.retry_after(key, limit=2) == 29


def test_keys_are_counted_separately():
    limiter = SlidingWindowLimiter(FakeClock())
    limiter.record(("1.1.1.1", "turns"))

    assert limiter.retry_after(("1.1.1.1", "turns"), limit=1) > 0
    assert limiter.retry_after(("2.2.2.2", "turns"), limit=1) == 0
    assert limiter.retry_after(("1.1.1.1", "analysis"), limit=1) == 0


def test_abandoned_addresses_are_dropped_so_memory_stays_bounded(monkeypatch):
    monkeypatch.setattr("app.core.ratelimit.MAX_TRACKED_KEYS", 5)
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock)
    for n in range(5):
        limiter.record((f"9.9.9.{n}", "general"))

    clock.now += 120
    limiter.record(("8.8.8.8", "general"))

    assert len(limiter._hits) == 1


# --- which address counts as the client ------------------------------------


def test_without_a_proxy_the_socket_address_is_used():
    assert client_ip(scope_with("6.6.6.6"), trusted_hops=0) == "10.0.0.1"


def test_behind_one_proxy_the_address_it_appended_is_used():
    assert client_ip(scope_with("203.0.113.9"), trusted_hops=1) == "203.0.113.9"


def test_a_forged_left_entry_is_ignored():
    forged = scope_with("6.6.6.6, 203.0.113.9")

    assert client_ip(forged, trusted_hops=1) == "203.0.113.9"


def test_a_missing_header_falls_back_to_the_socket_address():
    assert client_ip(scope_with(None), trusted_hops=1) == "10.0.0.1"


def test_a_header_shorter_than_the_proxy_chain_falls_back_to_the_socket():
    assert client_ip(scope_with("203.0.113.9"), trusted_hops=2) == "10.0.0.1"


# --- through the real app ---------------------------------------------------


@pytest.fixture
def limits(request, monkeypatch):
    """Turns limiting on with the values a test asks for. Fixtures are built in
    argument order, so listing this before `client` means the app is created
    after the environment is set."""
    from app.config import get_settings

    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    for name, value in request.param.items():
        monkeypatch.setenv(name.upper(), str(value))
    get_settings.cache_clear()


def with_limits(**values):
    return pytest.mark.parametrize("limits", [values], indirect=True)


async def text_turn(client, session_id, headers=None):
    return await client.post(
        f"/api/v1/sessions/{session_id}/turns/text",
        json={"text": "hello there"},
        headers=headers or {},
    )


@with_limits(rate_limit_turns_per_minute=3, rate_limit_general_per_minute=100)
async def test_turns_beyond_the_limit_get_429_with_the_normal_error_shape(
    limits, client
):
    session_id = (await client.post("/api/v1/sessions")).json()["id"]

    for _ in range(3):
        assert (await text_turn(client, session_id)).status_code == 200
    response = await text_turn(client, session_id)

    assert response.status_code == 429
    body = response.json()["error"]
    assert body["code"] == "RATE_LIMITED"
    assert body["details"]["retry_after_seconds"] >= 1
    assert int(response.headers["retry-after"]) >= 1
    assert "second" in body["message"]


@with_limits(rate_limit_turns_per_minute=1, rate_limit_general_per_minute=100)
async def test_a_rejection_still_carries_cors_headers(limits, client):
    """Without them the browser reports a network failure and hides the message."""
    origin = {"Origin": "http://localhost:8080"}
    session_id = (await client.post("/api/v1/sessions")).json()["id"]
    await text_turn(client, session_id, origin)

    response = await text_turn(client, session_id, origin)

    assert response.status_code == 429
    assert response.headers["access-control-allow-origin"] == "http://localhost:8080"


@with_limits(rate_limit_general_per_minute=2)
async def test_the_health_check_is_never_limited(limits, client):
    statuses = [(await client.get("/health")).status_code for _ in range(6)]

    assert statuses == [200] * 6


@with_limits(rate_limit_general_per_minute=1)
async def test_preflight_requests_are_never_limited(limits, client):
    headers = {
        "Origin": "http://localhost:8080",
        "Access-Control-Request-Method": "POST",
    }

    statuses = [
        (await client.options("/api/v1/sessions", headers=headers)).status_code
        for _ in range(5)
    ]

    assert statuses == [200] * 5


@with_limits(
    rate_limit_analysis_per_minute=1,
    rate_limit_turns_per_minute=10,
    rate_limit_general_per_minute=100,
)
async def test_analysis_has_its_own_limit_separate_from_turns(limits, client):
    session_id = (await client.post("/api/v1/sessions")).json()["id"]
    await text_turn(client, session_id)
    url = f"/api/v1/sessions/{session_id}/analysis/fluency"

    first = await client.post(url)
    second = await client.post(url)
    turn_after = await text_turn(client, session_id)

    assert first.status_code == 200
    assert second.status_code == 429
    assert turn_after.status_code == 200


@with_limits(rate_limit_general_per_minute=3)
async def test_the_general_limit_covers_everything_else(limits, client):
    statuses = [(await client.post("/api/v1/sessions")).status_code for _ in range(4)]

    assert statuses == [201, 201, 201, 429]


@with_limits(rate_limit_general_per_minute=2, trusted_proxy_hops=1)
async def test_different_clients_behind_a_proxy_have_separate_limits(limits, client):
    alice = {"X-Forwarded-For": "198.51.100.1"}
    bob = {"X-Forwarded-For": "198.51.100.2"}

    for _ in range(2):
        assert (await client.post("/api/v1/sessions", headers=alice)).status_code == 201

    assert (await client.post("/api/v1/sessions", headers=alice)).status_code == 429
    assert (await client.post("/api/v1/sessions", headers=bob)).status_code == 201


@with_limits(rate_limit_general_per_minute=2, trusted_proxy_hops=1)
async def test_rotating_a_forged_address_does_not_evade_the_limit(limits, client):
    statuses = []
    for n in range(4):
        headers = {"X-Forwarded-For": f"6.6.6.{n}, 198.51.100.1"}
        statuses.append((await client.post("/api/v1/sessions", headers=headers)).status_code)

    assert statuses == [201, 201, 429, 429]


@with_limits(rate_limit_general_per_minute=2, trusted_proxy_hops=0)
async def test_the_header_is_ignored_when_no_proxy_is_trusted(limits, client):
    statuses = []
    for n in range(3):
        headers = {"X-Forwarded-For": f"6.6.6.{n}"}
        statuses.append((await client.post("/api/v1/sessions", headers=headers)).status_code)

    assert statuses == [201, 201, 429]


@with_limits(rate_limit_general_per_minute=0)
async def test_a_limit_of_zero_turns_that_limit_off(limits, client):
    statuses = [(await client.post("/api/v1/sessions")).status_code for _ in range(5)]

    assert statuses == [201] * 5


async def test_limiting_can_be_disabled_entirely(monkeypatch, client):
    statuses = [(await client.post("/api/v1/sessions")).status_code for _ in range(5)]

    assert statuses == [201] * 5
