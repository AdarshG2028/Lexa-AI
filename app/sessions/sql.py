import json
import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import StorageError
from app.db.models import SessionRow, TurnRow
from app.models import (
    AudioRef,
    Session,
    SessionStatus,
    Speaker,
    Turn,
    WordTiming,
)

logger = logging.getLogger(__name__)


class SqlSessionRepository:
    """Database-backed session storage.

    Implements the same `SessionRepository` protocol as the in-memory store, so
    the conversation service is unchanged by the swap. ORM rows are mapped to
    the domain models rather than leaking into the rest of the application.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, session: Session) -> Session:
        try:
            async with self._session_factory() as db:
                db.add(_to_row(session))
                await db.commit()
        except SQLAlchemyError as exc:
            logger.exception("Failed to create session %s", session.id)
            raise StorageError("The conversation could not be saved.") from exc
        return session

    async def get(self, session_id: str) -> Session | None:
        try:
            async with self._session_factory() as db:
                row = await db.scalar(
                    select(SessionRow).where(SessionRow.id == session_id)
                )
                return _to_domain(row) if row else None
        except SQLAlchemyError as exc:
            logger.exception("Failed to read session %s", session_id)
            raise StorageError("The conversation could not be read.") from exc

    async def save(self, session: Session) -> Session:
        """Updates the session and appends any turns not yet stored.

        Turns are immutable once written, so persisting a turn is an insert
        keyed on its id rather than a rewrite of the whole conversation.
        """
        try:
            async with self._session_factory() as db:
                row = await db.scalar(
                    select(SessionRow).where(SessionRow.id == session.id)
                )
                if row is None:
                    db.add(_to_row(session))
                    await db.commit()
                    return session

                row.status = session.status.value
                row.user_id = session.user_id
                row.started_at = session.started_at
                row.last_activity_at = session.last_activity_at
                row.ended_at = session.ended_at

                stored = {turn.id for turn in row.turns}
                for turn in session.turns:
                    if turn.id not in stored:
                        row.turns.append(_turn_to_row(session.id, turn))

                await db.commit()
        except SQLAlchemyError as exc:
            logger.exception("Failed to save session %s", session.id)
            raise StorageError("The conversation could not be saved.") from exc
        return session


def _to_row(session: Session) -> SessionRow:
    return SessionRow(
        id=session.id,
        user_id=session.user_id,
        status=session.status.value,
        started_at=session.started_at,
        last_activity_at=session.last_activity_at,
        ended_at=session.ended_at,
        turns=[_turn_to_row(session.id, turn) for turn in session.turns],
    )


def _turn_to_row(session_id: str, turn: Turn) -> TurnRow:
    user = turn.user_audio
    assistant = turn.assistant_audio
    return TurnRow(
        id=turn.id,
        session_id=session_id,
        index=turn.index,
        created_at=turn.created_at,
        speaker=turn.speaker.value,
        transcript=turn.transcript,
        assistant_response=turn.assistant_response,
        user_audio_key=user.key if user else None,
        user_audio_format=user.format if user else None,
        user_audio_duration=user.duration_seconds if user else None,
        user_audio_size=user.size_bytes if user else None,
        assistant_audio_key=assistant.key if assistant else None,
        assistant_audio_format=assistant.format if assistant else None,
        assistant_audio_duration=assistant.duration_seconds if assistant else None,
        assistant_audio_size=assistant.size_bytes if assistant else None,
        words=json.dumps([w.model_dump() for w in turn.words]) if turn.words else None,
    )


def _to_domain(row: SessionRow) -> Session:
    return Session(
        id=row.id,
        user_id=row.user_id,
        status=SessionStatus(row.status),
        started_at=row.started_at,
        last_activity_at=row.last_activity_at,
        ended_at=row.ended_at,
        turns=[_turn_to_domain(turn) for turn in row.turns],
    )


def _turn_to_domain(row: TurnRow) -> Turn:
    return Turn(
        id=row.id,
        index=row.index,
        created_at=row.created_at,
        speaker=Speaker(row.speaker),
        transcript=row.transcript,
        assistant_response=row.assistant_response,
        user_audio=_audio_to_domain(
            row.user_audio_key, row.user_audio_format,
            row.user_audio_duration, row.user_audio_size,
        ),
        assistant_audio=_audio_to_domain(
            row.assistant_audio_key, row.assistant_audio_format,
            row.assistant_audio_duration, row.assistant_audio_size,
        ),
        words=_words_to_domain(row.words),
    )


def _words_to_domain(raw: str | None) -> list[WordTiming]:
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except ValueError:
        return []
    return [WordTiming(**i) for i in items if isinstance(i, dict)]


def _audio_to_domain(
    key: str | None, fmt: str | None, duration: float | None, size: int | None
) -> AudioRef | None:
    if key is None or fmt is None:
        return None
    return AudioRef(key=key, format=fmt, duration_seconds=duration, size_bytes=size)
