import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import analysis, conversation, health
from app.audio.processing import ffmpeg_available
from app.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.analysis.memory import InMemoryAnalysisRepository
from app.analysis.sql import SqlAnalysisRepository
from app.db.engine import create_engine, create_session_factory, create_tables
from app.providers.registry import ProviderRegistry
from app.sessions.memory import InMemorySessionRepository
from app.sessions.sql import SqlSessionRepository

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    if not ffmpeg_available():
        logger.warning(
            "ffmpeg/ffprobe not found on PATH. Audio turns will fail with "
            "CONFIG_ERROR until it is installed."
        )
    if settings.uses_groq and not settings.groq_api_key:
        logger.warning(
            "A Groq provider is selected but GROQ_API_KEY is empty. "
            "Set it in .env, or use the mock providers to run offline."
        )
    logger.info(
        "Providers: stt=%s llm=%s tts=%s",
        settings.stt_provider, settings.llm_provider, settings.tts_provider,
    )

    app.state.registry = ProviderRegistry(settings)
    app.state.engine = None

    if settings.session_store == "database":
        app.state.engine = create_engine(settings.database_url)
        await create_tables(app.state.engine)
        factory = create_session_factory(app.state.engine)
        app.state.session_repository = SqlSessionRepository(factory)
        app.state.analysis_repository = SqlAnalysisRepository(factory)
        logger.info("Sessions persisted to %s", settings.database_url)
    else:
        app.state.session_repository = InMemorySessionRepository()
        app.state.analysis_repository = InMemoryAnalysisRepository()
        logger.warning("Sessions are in memory only and are lost on restart.")

    try:
        yield
    finally:
        await app.state.registry.close()
        if app.state.engine is not None:
            await app.state.engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Voice Conversation & Speech Coach",
        description="Backend API. Phase 1: speak to the AI and hear it reply.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # No cookies or auth headers are used, so credentials stay off: allowing
    # them would force every origin to be named exactly and buys nothing here.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(conversation.router)
    app.include_router(analysis.router)

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "The request body or parameters were invalid.",
                    "details": {"issues": exc.errors()},
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                    "details": {},
                }
            },
        )

    return app


app = create_app()
