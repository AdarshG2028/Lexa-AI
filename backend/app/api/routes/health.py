from fastapi import APIRouter

from app.api.deps import RegistryDep, SettingsDep
from app.audio.processing import ffmpeg_available
from app.core.errors import AppError

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health(settings: SettingsDep) -> dict:
    return {
        "status": "ok",
        "ffmpeg": ffmpeg_available(),
        "providers": {
            "stt": settings.stt_provider,
            "stt_language_routes": settings.stt_language_routes,
            "llm": settings.llm_provider,
            "tts": settings.tts_provider,
            "grammar": settings.grammar_provider,
            "vocabulary": settings.vocabulary_provider,
            "pronunciation": settings.pronunciation_provider,
            "alternatives": settings.alternatives_provider,
        },
    }


@router.get("/providers")
async def provider_health(registry: RegistryDep, settings: SettingsDep) -> dict:
    """Check each configured provider is reachable and that its configured
    model still exists, so a bad key or a retired model ID surfaces here
    rather than as a failure on the first real turn."""
    builders = {
        "stt": registry.speech_to_text,
        "llm": registry.llm,
        "tts": registry.text_to_speech,
        "grammar": registry.grammar,
        "vocabulary": registry.vocabulary,
        "pronunciation": registry.pronunciation,
        "alternatives": registry.alternatives,
    }

    results: dict = {}
    healthy = True
    for role, build in builders.items():
        try:
            result = await build().check()
            ok = result.model_listed is not False
            healthy = healthy and ok
            results[role] = {"ok": ok, **result.model_dump(exclude_none=True)}
        except AppError as exc:
            healthy = False
            results[role] = {
                "ok": False,
                "provider": getattr(settings, f"{role}_provider"),
                "error": exc.code,
                "message": exc.message,
            }

    return {"status": "ok" if healthy else "degraded", "checks": results}
