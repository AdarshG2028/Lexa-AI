from typing import Protocol, runtime_checkable

from app.models import GrammarAnalysis


@runtime_checkable
class AnalysisRepository(Protocol):
    """Stores analysis results. Re-running an analysis replaces the previous
    one for that session rather than accumulating duplicates."""

    async def save_grammar(self, analysis: GrammarAnalysis) -> GrammarAnalysis: ...

    async def get_grammar(self, session_id: str) -> GrammarAnalysis | None: ...
