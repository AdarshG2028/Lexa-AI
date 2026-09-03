from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class UtcDateTime(TypeDecorator):
    """Stores timezone-aware datetimes and reads them back the same way.

    SQLite has no native timezone support and would silently return naive
    datetimes, which then blow up when compared against aware ones during the
    session idle check. Values are normalised to UTC on the way in and given
    UTC back on the way out.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    turns: Mapped[list["TurnRow"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="TurnRow.index",
        lazy="selectin",
    )


class TurnRow(Base):
    __tablename__ = "turns"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    speaker: Mapped[str] = mapped_column(String(16), nullable=False)
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    user_audio_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_audio_format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    user_audio_duration: Mapped[float | None] = mapped_column(nullable=True)
    user_audio_size: Mapped[int | None] = mapped_column(nullable=True)

    assistant_audio_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assistant_audio_format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    assistant_audio_duration: Mapped[float | None] = mapped_column(nullable=True)
    assistant_audio_size: Mapped[int | None] = mapped_column(nullable=True)

    session: Mapped[SessionRow] = relationship(back_populates="turns")


class SpeechAnalysisRow(Base):
    """One analysis run over one conversation.

    Phase 4 fills in the grammar columns. Vocabulary, fluency and
    pronunciation add their own columns and child tables to this same row.
    """

    __tablename__ = "speech_analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    grammar_score: Mapped[int] = mapped_column(Integer, nullable=False)
    sentences_analyzed: Mapped[int] = mapped_column(Integer, nullable=False)
    words_analyzed: Mapped[int] = mapped_column(Integer, nullable=False)

    grammar_issues: Mapped[list["GrammarIssueRow"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class GrammarIssueRow(Base):
    __tablename__ = "grammar_issues"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("speech_analyses.id", ondelete="CASCADE"), index=True
    )
    turn_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    original: Mapped[str] = mapped_column(Text, nullable=False)
    corrected: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    analysis: Mapped[SpeechAnalysisRow] = relationship(
        back_populates="grammar_issues"
    )
