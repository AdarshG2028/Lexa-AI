import asyncio

from app.models import GrammarAnalysis


class InMemoryAnalysisRepository:
    """Analysis storage for runs that do not need a database."""

    def __init__(self) -> None:
        self._grammar: dict[str, GrammarAnalysis] = {}
        self._lock = asyncio.Lock()

    async def save_grammar(self, analysis: GrammarAnalysis) -> GrammarAnalysis:
        async with self._lock:
            self._grammar[analysis.session_id] = analysis
        return analysis

    async def get_grammar(self, session_id: str) -> GrammarAnalysis | None:
        async with self._lock:
            return self._grammar.get(session_id)
