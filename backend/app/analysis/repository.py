from typing import Protocol, runtime_checkable

from app.models import (
    FluencyAnalysis,
    GrammarAnalysis,
    PronunciationAnalysis,
    VocabularyAnalysis,
)


@runtime_checkable
class AnalysisRepository(Protocol):
    """Stores analysis results.

    A conversation has one analysis record made of independent sections.
    Saving one section replaces only that section, so grammar and vocabulary
    can be run in any order without overwriting each other.
    """

    async def save_grammar(self, analysis: GrammarAnalysis) -> GrammarAnalysis: ...

    async def get_grammar(self, session_id: str) -> GrammarAnalysis | None: ...

    async def save_vocabulary(
        self, analysis: VocabularyAnalysis
    ) -> VocabularyAnalysis: ...

    async def get_vocabulary(self, session_id: str) -> VocabularyAnalysis | None: ...

    async def save_fluency(self, analysis: FluencyAnalysis) -> FluencyAnalysis: ...

    async def get_fluency(self, session_id: str) -> FluencyAnalysis | None: ...

    async def save_pronunciation(
        self, analysis: PronunciationAnalysis
    ) -> PronunciationAnalysis: ...

    async def get_pronunciation(
        self, session_id: str
    ) -> PronunciationAnalysis | None: ...
