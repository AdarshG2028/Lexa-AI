from fastapi import APIRouter

from app.api.deps import (
    AlternativesRepositoryDep,
    AlternativesServiceDep,
    ConversationServiceDep,
)
from app.core.errors import AnalysisNotFoundError
from app.models import EnglishAlternativesAnalysis

router = APIRouter(prefix="/api/v1/sessions", tags=["language bridge"])


@router.post(
    "/{session_id}/analysis/english-alternatives",
    response_model=EnglishAlternativesAnalysis,
)
async def run_english_alternatives(
    session_id: str,
    conversation: ConversationServiceDep,
    alternatives: AlternativesServiceDep,
    repository: AlternativesRepositoryDep,
) -> EnglishAlternativesAnalysis:
    """English alternatives for the phrases and harder words a learner said
    in their own language. Only for `language_bridge` conversations; an
    English one is refused rather than analysed into nonsense."""
    session = await conversation.get_session(session_id)
    analysis = await alternatives.analyze(session)
    return await repository.save(analysis)


@router.get(
    "/{session_id}/analysis/english-alternatives",
    response_model=EnglishAlternativesAnalysis,
)
async def get_english_alternatives(
    session_id: str,
    conversation: ConversationServiceDep,
    repository: AlternativesRepositoryDep,
) -> EnglishAlternativesAnalysis:
    """The stored report, or 404 if it has not been run yet."""
    await conversation.get_session(session_id)
    analysis = await repository.get(session_id)
    if analysis is None:
        raise AnalysisNotFoundError(session_id=session_id)
    return analysis
