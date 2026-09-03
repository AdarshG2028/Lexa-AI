from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from app.analysis.grammar import GrammarAnalysisService
from app.analysis.repository import AnalysisRepository
from app.config import Settings, get_settings
from app.providers.registry import ProviderRegistry
from app.services.conversation_service import ConversationService
from app.sessions.repository import SessionRepository
from app.storage.base import AudioStorage
from app.storage.local import LocalAudioStorage

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_registry(request: Request) -> ProviderRegistry:
    """The registry is built once in the app lifespan and closed with it, so
    the shared HTTP client has a lifetime tied to the application."""
    return request.app.state.registry


def get_session_repository(request: Request) -> SessionRepository:
    """In-memory or database backed, decided by configuration at startup."""
    return request.app.state.session_repository


@lru_cache
def get_audio_storage() -> AudioStorage:
    return LocalAudioStorage(get_settings().storage_local_path)


def get_analysis_repository(request: Request) -> AnalysisRepository:
    return request.app.state.analysis_repository


def get_grammar_service(
    registry: Annotated[ProviderRegistry, Depends(get_registry)],
) -> GrammarAnalysisService:
    return GrammarAnalysisService(registry.grammar())


def get_conversation_service(
    settings: SettingsDep,
    registry: Annotated[ProviderRegistry, Depends(get_registry)],
    sessions: Annotated[SessionRepository, Depends(get_session_repository)],
    storage: Annotated[AudioStorage, Depends(get_audio_storage)],
) -> ConversationService:
    return ConversationService(
        stt=registry.speech_to_text(),
        llm=registry.llm(),
        tts=registry.text_to_speech(),
        sessions=sessions,
        storage=storage,
        settings=settings,
    )


ConversationServiceDep = Annotated[
    ConversationService, Depends(get_conversation_service)
]
RegistryDep = Annotated[ProviderRegistry, Depends(get_registry)]
GrammarServiceDep = Annotated[GrammarAnalysisService, Depends(get_grammar_service)]
AnalysisRepositoryDep = Annotated[
    AnalysisRepository, Depends(get_analysis_repository)
]
