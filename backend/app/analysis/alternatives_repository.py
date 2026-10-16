import asyncio
import logging
from typing import Protocol, runtime_checkable
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import StorageError
from app.db.models import EnglishAlternativeRow, EnglishAlternativesRow
from app.models import (
    AlternativeKind,
    EnglishAlternative,
    EnglishAlternativesAnalysis,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class EnglishAlternativesRepository(Protocol):
    """Stores the language-bridge report. One per conversation; running the
    analysis again replaces it."""

    async def save(
        self, analysis: EnglishAlternativesAnalysis
    ) -> EnglishAlternativesAnalysis: ...

    async def get(self, session_id: str) -> EnglishAlternativesAnalysis | None: ...


class InMemoryEnglishAlternativesRepository:
    def __init__(self) -> None:
        self._analyses: dict[str, EnglishAlternativesAnalysis] = {}
        self._lock = asyncio.Lock()

    async def save(
        self, analysis: EnglishAlternativesAnalysis
    ) -> EnglishAlternativesAnalysis:
        async with self._lock:
            self._analyses[analysis.session_id] = analysis
        return analysis

    async def get(self, session_id: str) -> EnglishAlternativesAnalysis | None:
        async with self._lock:
            return self._analyses.get(session_id)


class SqlEnglishAlternativesRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(
        self, analysis: EnglishAlternativesAnalysis
    ) -> EnglishAlternativesAnalysis:
        try:
            await self._upsert(analysis)
        except SQLAlchemyError as exc:
            logger.exception(
                "Failed to save English alternatives for %s", analysis.session_id
            )
            raise StorageError("The analysis could not be saved.") from exc
        return analysis

    async def _upsert(self, analysis: EnglishAlternativesAnalysis) -> None:
        """Replaces the session's report, creating it the first time.

        Two requests for the same new session can both find no row and both
        insert it, and the database accepts only one; the loser retries once
        against the committed row and updates it instead of reporting a
        failure for a write that in effect succeeded.

        Two requests re-running an existing report are the other case. The
        parent row is locked for the transaction, and its items are deleted
        by statement rather than through the loaded collection: a writer that
        had already loaded the old items would otherwise delete rows the other
        had just removed, match nothing, and leave both writers' items behind.
        """
        for attempt in range(2):
            try:
                async with self._session_factory() as db:
                    row = await db.scalar(
                        select(EnglishAlternativesRow)
                        .where(EnglishAlternativesRow.session_id == analysis.session_id)
                        .with_for_update()
                    )
                    if row is None:
                        row = EnglishAlternativesRow(
                            id=uuid4().hex,
                            session_id=analysis.session_id,
                            spoken_language=analysis.spoken_language,
                            provider=analysis.provider,
                            created_at=analysis.created_at,
                            turns_analyzed=analysis.turns_analyzed,
                            note=analysis.note,
                        )
                        db.add(row)
                        await db.flush()
                    else:
                        row.spoken_language = analysis.spoken_language
                        row.provider = analysis.provider
                        row.created_at = analysis.created_at
                        row.turns_analyzed = analysis.turns_analyzed
                        row.note = analysis.note
                        await db.execute(
                            delete(EnglishAlternativeRow).where(
                                EnglishAlternativeRow.analysis_id == row.id
                            )
                        )

                    db.add_all(
                        EnglishAlternativeRow(
                            id=item.id,
                            analysis_id=row.id,
                            position=position,
                            turn_id=item.turn_id,
                            original=item.original,
                            english=item.english,
                            kind=item.kind.value,
                            example=item.example,
                        )
                        for position, item in enumerate(analysis.items)
                    )
                    await db.commit()
                return
            except IntegrityError:
                if attempt == 1:
                    raise

    async def get(self, session_id: str) -> EnglishAlternativesAnalysis | None:
        try:
            async with self._session_factory() as db:
                row = await db.scalar(
                    select(EnglishAlternativesRow).where(
                        EnglishAlternativesRow.session_id == session_id
                    )
                )
        except SQLAlchemyError as exc:
            logger.exception("Failed to read English alternatives for %s", session_id)
            raise StorageError("The analysis could not be read.") from exc

        if row is None:
            return None
        return EnglishAlternativesAnalysis(
            session_id=row.session_id,
            spoken_language=row.spoken_language,
            provider=row.provider,
            created_at=row.created_at,
            turns_analyzed=row.turns_analyzed,
            note=row.note or "",
            items=[
                EnglishAlternative(
                    id=item.id,
                    turn_id=item.turn_id,
                    original=item.original,
                    english=item.english,
                    kind=AlternativeKind(item.kind),
                    example=item.example or "",
                )
                for item in row.items
            ],
        )
