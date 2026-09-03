from fastapi import APIRouter

from app.api.deps import (
    AnalysisRepositoryDep,
    ConversationServiceDep,
    GrammarServiceDep,
)
from app.core.errors import AnalysisNotFoundError
from app.models import GrammarAnalysis

router = APIRouter(prefix="/api/v1/sessions", tags=["analysis"])


@router.post("/{session_id}/analysis/grammar", response_model=GrammarAnalysis)
async def run_grammar_analysis(
    session_id: str,
    conversation: ConversationServiceDep,
    grammar: GrammarServiceDep,
    analyses: AnalysisRepositoryDep,
) -> GrammarAnalysis:
    """Analyses what the user said and stores the result.

    Runs synchronously: a conversation's worth of text is one provider call.
    If analysis grows to include audio models, this is the endpoint that moves
    behind a background job.
    """
    session = await conversation.get_session(session_id)
    analysis = await grammar.analyze(session)
    return await analyses.save_grammar(analysis)


@router.get("/{session_id}/analysis/grammar", response_model=GrammarAnalysis)
async def get_grammar_analysis(
    session_id: str,
    conversation: ConversationServiceDep,
    analyses: AnalysisRepositoryDep,
) -> GrammarAnalysis:
    """The stored analysis, or 404 if it has not been run yet."""
    await conversation.get_session(session_id)
    analysis = await analyses.get_grammar(session_id)
    if analysis is None:
        raise AnalysisNotFoundError(session_id=session_id)
    return analysis
