async def test_health_reports_configured_providers(client):
    response = await client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["providers"] == {
        "stt": "mock", "llm": "mock", "tts": "mock", "grammar": "mock",
        "vocabulary": "mock",
    }


async def test_provider_health_passes_with_mocks(client):
    response = await client.get("/health/providers")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert all(check["ok"] for check in body["checks"].values())


async def test_provider_health_reports_degraded_when_a_model_is_missing(app, client):
    """A retired model ID must show up here, not on the first real turn."""
    from app.api.deps import get_registry
    from app.models import ProviderCheck

    class StaleTTS:
        name = "groq"

        async def check(self) -> ProviderCheck:
            return ProviderCheck(
                provider="groq",
                model="retired-model",
                model_listed=False,
                note="This model ID was not in the provider's model list.",
            )

    registry = app.dependency_overrides[get_registry]()
    registry.text_to_speech = StaleTTS
    app.dependency_overrides[get_registry] = lambda: registry

    body = (await client.get("/health/providers")).json()
    assert body["status"] == "degraded"
    assert body["checks"]["tts"]["ok"] is False
    assert body["checks"]["llm"]["ok"] is True
