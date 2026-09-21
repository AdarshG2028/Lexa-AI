from fastapi import APIRouter

from app.api.deps import (
    AnalysisRepositoryDep,
    ConversationServiceDep,
    GrammarServiceDep,
    FluencyServiceDep,
    PronunciationServiceDep,
    VocabularyServiceDep,
)
from app.core.errors import AnalysisNotFoundError
from app.models import (
    FluencyAnalysis,
    GrammarAnalysis,
    PronunciationAnalysis,
    VocabularyAnalysis,
)

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


@router.post("/{session_id}/analysis/vocabulary", response_model=VocabularyAnalysis)
async def run_vocabulary_analysis(
    session_id: str,
    conversation: ConversationServiceDep,
    vocabulary: VocabularyServiceDep,
    analyses: AnalysisRepositoryDep,
) -> VocabularyAnalysis:
    """Measures word use and asks the provider for better alternatives."""
    session = await conversation.get_session(session_id)
    analysis = await vocabulary.analyze(session)
    return await analyses.save_vocabulary(analysis)


@router.get("/{session_id}/analysis/vocabulary", response_model=VocabularyAnalysis)
async def get_vocabulary_analysis(
    session_id: str,
    conversation: ConversationServiceDep,
    analyses: AnalysisRepositoryDep,
) -> VocabularyAnalysis:
    await conversation.get_session(session_id)
    analysis = await analyses.get_vocabulary(session_id)
    if analysis is None:
        raise AnalysisNotFoundError(session_id=session_id)
    return analysis


@router.post("/{session_id}/analysis/fluency", response_model=FluencyAnalysis)
async def run_fluency_analysis(
    session_id: str,
    conversation: ConversationServiceDep,
    fluency: FluencyServiceDep,
    analyses: AnalysisRepositoryDep,
) -> FluencyAnalysis:
    """Measures speaking rate, pauses, fillers and false starts from the
    word timings captured during transcription. No model is called."""
    session = await conversation.get_session(session_id)
    analysis = fluency.analyze(session)
    return await analyses.save_fluency(analysis)


@router.get("/{session_id}/analysis/fluency", response_model=FluencyAnalysis)
async def get_fluency_analysis(
    session_id: str,
    conversation: ConversationServiceDep,
    analyses: AnalysisRepositoryDep,
) -> FluencyAnalysis:
    await conversation.get_session(session_id)
    analysis = await analyses.get_fluency(session_id)
    if analysis is None:
        raise AnalysisNotFoundError(session_id=session_id)
    return analysis


@router.post(
    "/{session_id}/analysis/pronunciation", response_model=PronunciationAnalysis
)
async def run_pronunciation_analysis(
    session_id: str,
    conversation: ConversationServiceDep,
    pronunciation: PronunciationServiceDep,
    analyses: AnalysisRepositoryDep,
) -> PronunciationAnalysis:
    """Compares the sounds produced against the sounds the words require.

    Runs a phoneme model over the stored audio, so this is by far the slowest
    endpoint - seconds per turn, and slower still on the first call while the
    weights load.
    """
    session = await conversation.get_session(session_id)
    analysis = await pronunciation.analyze(session)
    return await analyses.save_pronunciation(analysis)


@router.get(
    "/{session_id}/analysis/pronunciation", response_model=PronunciationAnalysis
)
async def get_pronunciation_analysis(
    session_id: str,
    conversation: ConversationServiceDep,
    analyses: AnalysisRepositoryDep,
) -> PronunciationAnalysis:
    await conversation.get_session(session_id)
    analysis = await analyses.get_pronunciation(session_id)
    if analysis is None:
        raise AnalysisNotFoundError(session_id=session_id)
    return analysis
