"""The browser blocks every cross-origin call unless the server names the
origin, so this is the difference between a working frontend and a blank page.
"""


async def test_preflight_from_the_frontend_origin_is_accepted(client):
    response = await client.options(
        "/api/v1/sessions",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8080"


async def test_actual_request_carries_permission_back(client):
    response = await client.post(
        "/api/v1/sessions", json={}, headers={"Origin": "http://localhost:8080"}
    )

    assert response.status_code == 201
    assert response.headers["access-control-allow-origin"] == "http://localhost:8080"


async def test_unlisted_origin_gets_no_permission(client):
    response = await client.post(
        "/api/v1/sessions", json={}, headers={"Origin": "http://evil.example"}
    )

    assert "access-control-allow-origin" not in response.headers



async def test_origin_regex_admits_preview_subdomains(monkeypatch):
    """Vercel gives every preview deployment its own subdomain, so the exact
    list can never cover them; the regex setting is what does."""
    from httpx import ASGITransport, AsyncClient

    from app.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("CORS_ALLOWED_ORIGIN_REGEX", r"https://lexa-.*\.vercel\.app")
    get_settings.cache_clear()
    try:
        application = create_app()
    finally:
        get_settings.cache_clear()

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as c:
        allowed = await c.options(
            "/api/v1/sessions",
            headers={
                "Origin": "https://lexa-git-abc123-me.vercel.app",
                "Access-Control-Request-Method": "POST",
            },
        )
        refused = await c.options(
            "/api/v1/sessions",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert allowed.headers["access-control-allow-origin"] == (
        "https://lexa-git-abc123-me.vercel.app"
    )
    assert "access-control-allow-origin" not in refused.headers
