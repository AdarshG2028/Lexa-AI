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

    # Word timings as JSON. Fluency is analysed after the conversation, so the
    # timings must be kept when the transcription happens - re-transcribing
    # later would cost another provider call for data we already had.
    words: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped[SessionRow] = relationship(back_populates="turns")


class SpeechAnalysisRow(Base):
    """One analysis record per conversation, filled in section by section.

    Grammar and vocabulary are run by separate endpoints, so each section is
    nullable and is written without disturbing the others. Fluency and
    pronunciation add their own columns to this same row.
    """

    __tablename__ = "speech_analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    grammar_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    grammar_created_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    grammar_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sentences_analyzed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    words_analyzed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    vocabulary_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    vocabulary_created_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    vocabulary_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vocabulary_words: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unique_words: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lexical_diversity: Mapped[float | None] = mapped_column(Float, nullable=True)

    fluency_created_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    fluency_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fluency_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    timed_words: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analyzed_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    speaking_rate_wpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    articulation_rate_wpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    pause_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    long_pause_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_pause_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    filler_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    repetition_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    restart_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    pronunciation_provider: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    pronunciation_created_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    pronunciation_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pronunciation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    pronunciation_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    pronunciation_words: Mapped[int | None] = mapped_column(Integer, nullable=True)
    substitutions_found: Mapped[int | None] = mapped_column(Integer, nullable=True)

    grammar_issues: Mapped[list["GrammarIssueRow"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    vocabulary_issues: Mapped[list["VocabularyIssueRow"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    fluency_findings: Mapped[list["FluencyFindingRow"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    pronunciation_issues: Mapped[list["PronunciationIssueRow"]] = relationship(
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


class VocabularyIssueRow(Base):
    __tablename__ = "vocabulary_issues"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("speech_analyses.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False)
    example: Mapped[str] = mapped_column(Text, nullable=False)
    suggestions: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    analysis: Mapped[SpeechAnalysisRow] = relationship(
        back_populates="vocabulary_issues"
    )


class FluencyFindingRow(Base):
    """One fluency habit and how often it occurred.

    Kept as rows rather than a JSON blob so Phase 9 can ask which filler words
    recur across a learner's sessions.
    """

    __tablename__ = "fluency_findings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("speech_analyses.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    text: Mapped[str] = mapped_column(String(255), nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)

    analysis: Mapped[SpeechAnalysisRow] = relationship(
        back_populates="fluency_findings"
    )


class PronunciationIssueRow(Base):
    """A recurring phoneme substitution.

    Indexed on the phoneme pair so Phase 9 can ask whether a learner's /th/
    is improving from one session to the next.
    """

    __tablename__ = "pronunciation_issues"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("speech_analyses.id", ondelete="CASCADE"), index=True
    )
    expected_phoneme: Mapped[str] = mapped_column(String(16), nullable=False,
                                                  index=True)
    detected_phoneme: Mapped[str] = mapped_column(String(16), nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    affected_words: Mapped[str] = mapped_column(Text, nullable=False)
    practice_words: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    analysis: Mapped[SpeechAnalysisRow] = relationship(
        back_populates="pronunciation_issues"
    )
