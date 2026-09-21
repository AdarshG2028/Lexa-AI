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
