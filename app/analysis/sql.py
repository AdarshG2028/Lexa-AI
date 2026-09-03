import logging
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import StorageError
from app.db.models import GrammarIssueRow, SpeechAnalysisRow
from app.models import GrammarAnalysis, GrammarCategory, GrammarIssue

logger = logging.getLogger(__name__)


class SqlAnalysisRepository:
    """Database-backed analysis storage."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_grammar(self, analysis: GrammarAnalysis) -> GrammarAnalysis:
        try:
            async with self._session_factory() as db:
                await db.execute(
                    delete(SpeechAnalysisRow).where(
                        SpeechAnalysisRow.session_id == analysis.session_id
                    )
                )
                db.add(
                    SpeechAnalysisRow(
                        id=uuid4().hex,
                        session_id=analysis.session_id,
                        created_at=analysis.created_at,
                        provider=analysis.provider,
                        grammar_score=analysis.grammar_score,
                        sentences_analyzed=analysis.sentences_analyzed,
                        words_analyzed=analysis.words_analyzed,
                        grammar_issues=[
                            GrammarIssueRow(
                                id=issue.id,
                                turn_id=issue.turn_id,
                                original=issue.original,
                                corrected=issue.corrected,
                                explanation=issue.explanation,
                                category=issue.category.value,
                                confidence=issue.confidence,
                            )
                            for issue in analysis.issues
                        ],
                    )
                )
                await db.commit()
        except SQLAlchemyError as exc:
            logger.exception("Failed to save analysis for %s", analysis.session_id)
            raise StorageError("The analysis could not be saved.") from exc
        return analysis

    async def get_grammar(self, session_id: str) -> GrammarAnalysis | None:
        try:
            async with self._session_factory() as db:
                row = await db.scalar(
                    select(SpeechAnalysisRow)
                    .where(SpeechAnalysisRow.session_id == session_id)
                    .order_by(SpeechAnalysisRow.created_at.desc())
                    .limit(1)
                )
                return _to_domain(row) if row else None
        except SQLAlchemyError as exc:
            logger.exception("Failed to read analysis for %s", session_id)
            raise StorageError("The analysis could not be read.") from exc


def _to_domain(row: SpeechAnalysisRow) -> GrammarAnalysis:
    return GrammarAnalysis(
        session_id=row.session_id,
        provider=row.provider,
        created_at=row.created_at,
        sentences_analyzed=row.sentences_analyzed,
        words_analyzed=row.words_analyzed,
        grammar_score=row.grammar_score,
        issues=[
            GrammarIssue(
                id=issue.id,
                turn_id=issue.turn_id,
                original=issue.original,
                corrected=issue.corrected,
                explanation=issue.explanation,
                category=GrammarCategory(issue.category),
                confidence=issue.confidence,
            )
            for issue in row.grammar_issues
        ],
    )
