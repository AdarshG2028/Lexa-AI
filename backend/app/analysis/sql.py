import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import StorageError
from app.db.models import (
    FluencyFindingRow,
    GrammarIssueRow,
    PronunciationIssueRow,
    SpeechAnalysisRow,
    VocabularyIssueRow,
)
from app.models import (
    FluencyAnalysis,
    FluencyFinding,
    FluencyFindingType,
    GrammarAnalysis,
    GrammarCategory,
    PronunciationAnalysis,
    PronunciationIssue,
    GrammarIssue,
    VocabularyAnalysis,
    VocabularyIssue,
    VocabularyIssueType,
)

logger = logging.getLogger(__name__)


class SqlAnalysisRepository:
    """Database-backed analysis storage.

    A conversation has one analysis record, written section by section. Saving
    grammar leaves vocabulary untouched and the other way round, so the two
    endpoints can be run in either order or independently.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def _row_for(self, db: AsyncSession, session_id: str) -> SpeechAnalysisRow:
        row = await db.scalar(
            select(SpeechAnalysisRow).where(
                SpeechAnalysisRow.session_id == session_id
            )
        )
        if row is None:
            row = SpeechAnalysisRow(
                id=uuid4().hex, session_id=session_id, created_at=_utcnow()
            )
            db.add(row)
        return row

    async def _save(
        self, session_id: str, apply: Callable[[SpeechAnalysisRow], None]
    ) -> None:
        """Creates the session's analysis row on the first section saved, or
        updates it on every one after. Two sections saved close together (the
        report page runs fluency, grammar and vocabulary back to back, and a
        page refresh mid-run can overlap a fresh set of requests with ones
        still in flight) can both see no row yet and both try to create it;
        the database accepts only one, and the loser retries once against the
        row the winner just committed - so the loser updates instead of
        failing, rather than surfacing as "could not be saved" when the data
        was in fact saved.
        """
        for attempt in range(2):
            try:
                async with self._session_factory() as db:
                    row = await self._row_for(db, session_id)
                    apply(row)
                    await db.commit()
                return
            except IntegrityError:
                if attempt == 1:
                    raise

    async def save_grammar(self, analysis: GrammarAnalysis) -> GrammarAnalysis:
        def apply(row: SpeechAnalysisRow) -> None:
            row.grammar_provider = analysis.provider
            row.grammar_created_at = analysis.created_at
            row.grammar_score = analysis.grammar_score
            row.sentences_analyzed = analysis.sentences_analyzed
            row.words_analyzed = analysis.words_analyzed
            row.grammar_issues = [
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
            ]

        try:
            await self._save(analysis.session_id, apply)
        except SQLAlchemyError as exc:
            logger.exception("Failed to save grammar for %s", analysis.session_id)
            raise StorageError("The analysis could not be saved.") from exc
        return analysis

    async def get_grammar(self, session_id: str) -> GrammarAnalysis | None:
        row = await self._load(session_id)
        if row is None or row.grammar_score is None:
            return None
        return GrammarAnalysis(
            session_id=row.session_id,
            provider=row.grammar_provider or "unknown",
            created_at=row.grammar_created_at or row.created_at,
            sentences_analyzed=row.sentences_analyzed or 0,
            words_analyzed=row.words_analyzed or 0,
            grammar_score=row.grammar_score,
            issues=[
                GrammarIssue(
                    id=i.id,
                    turn_id=i.turn_id,
                    original=i.original,
                    corrected=i.corrected,
                    explanation=i.explanation,
                    category=GrammarCategory(i.category),
                    confidence=i.confidence,
                )
                for i in row.grammar_issues
            ],
        )

    async def save_vocabulary(
        self, analysis: VocabularyAnalysis
    ) -> VocabularyAnalysis:
        def apply(row: SpeechAnalysisRow) -> None:
            row.vocabulary_provider = analysis.provider
            row.vocabulary_created_at = analysis.created_at
            row.vocabulary_score = analysis.vocabulary_score
            row.vocabulary_words = analysis.words_analyzed
            row.unique_words = analysis.unique_words
            row.lexical_diversity = analysis.lexical_diversity
            row.vocabulary_issues = [
                VocabularyIssueRow(
                    id=issue.id,
                    type=issue.type.value,
                    text=issue.text,
                    occurrences=issue.occurrences,
                    example=issue.example,
                    suggestions=json.dumps(issue.suggestions),
                    explanation=issue.explanation,
                    confidence=issue.confidence,
                )
                for issue in analysis.issues
            ]

        try:
            await self._save(analysis.session_id, apply)
        except SQLAlchemyError as exc:
            logger.exception("Failed to save vocabulary for %s", analysis.session_id)
            raise StorageError("The analysis could not be saved.") from exc
        return analysis

    async def get_vocabulary(self, session_id: str) -> VocabularyAnalysis | None:
        row = await self._load(session_id)
        if row is None or row.vocabulary_score is None:
            return None
        return VocabularyAnalysis(
            session_id=row.session_id,
            provider=row.vocabulary_provider or "unknown",
            created_at=row.vocabulary_created_at or row.created_at,
            words_analyzed=row.vocabulary_words or 0,
            unique_words=row.unique_words or 0,
            lexical_diversity=row.lexical_diversity or 0.0,
            vocabulary_score=row.vocabulary_score,
            issues=[
                VocabularyIssue(
                    id=i.id,
                    type=VocabularyIssueType(i.type),
                    text=i.text,
                    occurrences=i.occurrences,
                    example=i.example,
                    suggestions=_load_suggestions(i.suggestions),
                    explanation=i.explanation,
                    confidence=i.confidence,
                )
                for i in row.vocabulary_issues
            ],
        )

    async def save_fluency(self, analysis: FluencyAnalysis) -> FluencyAnalysis:
        def apply(row: SpeechAnalysisRow) -> None:
            row.fluency_created_at = analysis.created_at
            row.fluency_score = analysis.fluency_score
            row.fluency_note = analysis.note
            row.timed_words = analysis.timed_words
            row.analyzed_seconds = analysis.analyzed_seconds
            row.speaking_rate_wpm = analysis.speaking_rate_wpm
            row.articulation_rate_wpm = analysis.articulation_rate_wpm
            row.pause_count = analysis.pause_count
            row.long_pause_count = analysis.long_pause_count
            row.total_pause_seconds = analysis.total_pause_seconds
            row.filler_count = analysis.filler_count
            row.repetition_count = analysis.repetition_count
            row.restart_count = analysis.restart_count
            row.fluency_findings = [
                FluencyFindingRow(
                    id=f.id,
                    type=f.type.value,
                    text=f.text,
                    occurrences=f.occurrences,
                    detail=f.detail,
                )
                for f in analysis.findings
            ]

        try:
            await self._save(analysis.session_id, apply)
        except SQLAlchemyError as exc:
            logger.exception("Failed to save fluency for %s", analysis.session_id)
            raise StorageError("The analysis could not be saved.") from exc
        return analysis

    async def get_fluency(self, session_id: str) -> FluencyAnalysis | None:
        row = await self._load(session_id)
        if row is None or row.timed_words is None:
            return None
        return FluencyAnalysis(
            session_id=row.session_id,
            created_at=row.fluency_created_at or row.created_at,
            timed_words=row.timed_words,
            analyzed_seconds=row.analyzed_seconds or 0.0,
            speaking_rate_wpm=row.speaking_rate_wpm or 0.0,
            articulation_rate_wpm=row.articulation_rate_wpm or 0.0,
            pause_count=row.pause_count or 0,
            long_pause_count=row.long_pause_count or 0,
            total_pause_seconds=row.total_pause_seconds or 0.0,
            filler_count=row.filler_count or 0,
            repetition_count=row.repetition_count or 0,
            restart_count=row.restart_count or 0,
            fluency_score=row.fluency_score,
            note=row.fluency_note or "",
            findings=[
                FluencyFinding(
                    id=f.id,
                    type=FluencyFindingType(f.type),
                    text=f.text,
                    occurrences=f.occurrences,
                    detail=f.detail,
                )
                for f in row.fluency_findings
            ],
        )

    async def save_pronunciation(
        self, analysis: PronunciationAnalysis
    ) -> PronunciationAnalysis:
        def apply(row: SpeechAnalysisRow) -> None:
            row.pronunciation_provider = analysis.provider
            row.pronunciation_created_at = analysis.created_at
            row.pronunciation_score = analysis.pronunciation_score
            row.pronunciation_note = analysis.note
            row.pronunciation_seconds = analysis.analyzed_seconds
            row.pronunciation_words = analysis.words_analyzed
            row.substitutions_found = analysis.substitutions_found
            row.pronunciation_issues = [
                PronunciationIssueRow(
                    id=i.id,
                    expected_phoneme=i.expected_phoneme,
                    detected_phoneme=i.detected_phoneme,
                    occurrences=i.occurrences,
                    confidence=i.confidence,
                    affected_words=json.dumps(i.affected_words),
                    practice_words=json.dumps(i.practice_words),
                    explanation=i.explanation,
                )
                for i in analysis.issues
            ]

        try:
            await self._save(analysis.session_id, apply)
        except SQLAlchemyError as exc:
            logger.exception(
                "Failed to save pronunciation for %s", analysis.session_id
            )
            raise StorageError("The analysis could not be saved.") from exc
        return analysis

    async def get_pronunciation(
        self, session_id: str
    ) -> PronunciationAnalysis | None:
        row = await self._load(session_id)
        if row is None or row.pronunciation_provider is None:
            return None
        return PronunciationAnalysis(
            session_id=row.session_id,
            provider=row.pronunciation_provider,
            created_at=row.pronunciation_created_at or row.created_at,
            analyzed_seconds=row.pronunciation_seconds or 0.0,
            words_analyzed=row.pronunciation_words or 0,
            phonemes_analyzed=row.substitutions_found or 0,
            substitutions_found=row.substitutions_found or 0,
            pronunciation_score=row.pronunciation_score,
            note=row.pronunciation_note or "",
            issues=[
                PronunciationIssue(
                    id=i.id,
                    expected_phoneme=i.expected_phoneme,
                    detected_phoneme=i.detected_phoneme,
                    occurrences=i.occurrences,
                    confidence=i.confidence,
                    affected_words=_load_suggestions(i.affected_words),
                    practice_words=_load_suggestions(i.practice_words),
                    explanation=i.explanation,
                )
                for i in row.pronunciation_issues
            ],
        )

    async def _load(self, session_id: str) -> SpeechAnalysisRow | None:
        try:
            async with self._session_factory() as db:
                return await db.scalar(
                    select(SpeechAnalysisRow).where(
                        SpeechAnalysisRow.session_id == session_id
                    )
                )
        except SQLAlchemyError as exc:
            logger.exception("Failed to read analysis for %s", session_id)
            raise StorageError("The analysis could not be read.") from exc


def _load_suggestions(raw: str) -> list[str]:
    try:
        value = json.loads(raw)
    except ValueError:
        return []
    return [str(v) for v in value] if isinstance(value, list) else []


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
