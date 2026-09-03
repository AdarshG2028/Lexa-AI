from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field, computed_field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid4().hex


class Speaker(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"


class AudioRef(BaseModel):
    """Where an audio file lives, independent of the storage backend."""

    key: str
    format: str
    duration_seconds: float | None = None
    size_bytes: int | None = None


class Turn(BaseModel):
    id: str = Field(default_factory=_new_id)
    index: int
    created_at: datetime = Field(default_factory=_now)
    speaker: Speaker = Speaker.USER
    transcript: str
    assistant_response: str | None = None
    user_audio: AudioRef | None = None
    assistant_audio: AudioRef | None = None


class Session(BaseModel):
    id: str = Field(default_factory=_new_id)
    user_id: str | None = None
    status: SessionStatus = SessionStatus.ACTIVE
    started_at: datetime = Field(default_factory=_now)
    last_activity_at: datetime = Field(default_factory=_now)
    ended_at: datetime | None = None
    turns: list[Turn] = Field(default_factory=list)

    @computed_field
    @property
    def duration_seconds(self) -> float:
        end = self.ended_at or _now()
        return (end - self.started_at).total_seconds()

    @computed_field
    @property
    def turn_count(self) -> int:
        return len(self.turns)

    def idle_seconds(self, now: datetime | None = None) -> float:
        return ((now or _now()) - self.last_activity_at).total_seconds()


class Transcription(BaseModel):
    """Provider-neutral STT result."""

    text: str
    language: str | None = None
    duration_seconds: float | None = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatReply(BaseModel):
    """Provider-neutral LLM result."""

    text: str
    model: str | None = None


class SynthesizedSpeech(BaseModel):
    """Provider-neutral TTS result."""

    audio: bytes
    format: str
    provider: str


class GrammarCategory(str, Enum):
    TENSE = "tense"
    ARTICLES = "articles"
    PREPOSITIONS = "prepositions"
    SUBJECT_VERB_AGREEMENT = "subject_verb_agreement"
    PLURALS = "plurals"
    WORD_FORM = "word_form"
    SENTENCE_STRUCTURE = "sentence_structure"
    OTHER = "other"


class UserUtterance(BaseModel):
    """One thing the user said, with the turn it came from. Analysis works on
    these only; the assistant's speech is never assessed."""

    turn_id: str
    text: str


class GrammarIssue(BaseModel):
    """A single detected mistake. The original text is copied here verbatim;
    the stored transcript is never rewritten."""

    id: str = Field(default_factory=_new_id)
    turn_id: str | None = None
    original: str
    corrected: str
    explanation: str
    category: GrammarCategory = GrammarCategory.OTHER
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class GrammarAnalysis(BaseModel):
    session_id: str
    provider: str
    created_at: datetime = Field(default_factory=_now)
    sentences_analyzed: int
    words_analyzed: int
    grammar_score: int = Field(ge=0, le=100)
    issues: list[GrammarIssue] = Field(default_factory=list)

    @computed_field
    @property
    def issue_count(self) -> int:
        return len(self.issues)


class ProviderCheck(BaseModel):
    """Result of a provider preflight, in provider-neutral terms."""

    provider: str
    model: str | None = None
    model_listed: bool | None = None
    note: str | None = None


class TurnResult(BaseModel):
    """What the API returns after one conversational exchange."""

    session_id: str
    turn_id: str
    transcript: str
    reply_text: str
    audio_url: str
    tts_provider: str
    history_messages: int
    timings_ms: dict[str, int]
