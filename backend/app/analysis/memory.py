import asyncio

from app.models import (
    FluencyAnalysis,
    GrammarAnalysis,
    PronunciationAnalysis,
    VocabularyAnalysis,
)


class InMemoryAnalysisRepository:
    """Analysis storage for runs that do not need a database."""

    def __init__(self) -> None:
        self._grammar: dict[str, GrammarAnalysis] = {}
        self._vocabulary: dict[str, VocabularyAnalysis] = {}
        self._fluency: dict[str, FluencyAnalysis] = {}
        self._pronunciation: dict[str, PronunciationAnalysis] = {}
        self._lock = asyncio.Lock()

    async def save_grammar(self, analysis: GrammarAnalysis) -> GrammarAnalysis:
        async with self._lock:
            self._grammar[analysis.session_id] = analysis
        return analysis

    async def get_grammar(self, session_id: str) -> GrammarAnalysis | None:
        async with self._lock:
            return self._grammar.get(session_id)

    async def save_vocabulary(
        self, analysis: VocabularyAnalysis
    ) -> VocabularyAnalysis:
        async with self._lock:
            self._vocabulary[analysis.session_id] = analysis
        return analysis

    async def get_vocabulary(self, session_id: str) -> VocabularyAnalysis | None:
        async with self._lock:
            return self._vocabulary.get(session_id)

    async def save_fluency(self, analysis: FluencyAnalysis) -> FluencyAnalysis:
        async with self._lock:
            self._fluency[analysis.session_id] = analysis
        return analysis

    async def get_fluency(self, session_id: str) -> FluencyAnalysis | None:
        async with self._lock:
            return self._fluency.get(session_id)

    async def save_pronunciation(
        self, analysis: PronunciationAnalysis
    ) -> PronunciationAnalysis:
        async with self._lock:
            self._pronunciation[analysis.session_id] = analysis
        return analysis

    async def get_pronunciation(
        self, session_id: str
    ) -> PronunciationAnalysis | None:
        async with self._lock:
            return self._pronunciation.get(session_id)
