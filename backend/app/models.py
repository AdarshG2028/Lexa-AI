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


class WordTiming(BaseModel):
    """When one word was spoken. The basis of every fluency measurement."""

    word: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


class Turn(BaseModel):
    id: str = Field(default_factory=_new_id)
    index: int
    created_at: datetime = Field(default_factory=_now)
    speaker: Speaker = Speaker.USER
    transcript: str
    assistant_response: str | None = None
    user_audio: AudioRef | None = None
    assistant_audio: AudioRef | None = None
    words: list[WordTiming] = Field(default_factory=list)


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
    words: list[WordTiming] = Field(default_factory=list)


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


class VocabularyIssueType(str, Enum):
    REPEATED_WORD = "repeated_word"
    REPEATED_PHRASE = "repeated_phrase"
    BASIC_WORD = "basic_word"
    UNNATURAL_EXPRESSION = "unnatural_expression"


class VocabularyObservation(BaseModel):
    """A countable fact about word use, measured before any model is asked.

    Counting is arithmetic, not judgement, so it is done in code. The provider
    is only asked for the part that needs language sense: better alternatives.
    """

    type: VocabularyIssueType
    text: str
    occurrences: int
    example: str


class VocabularyIssue(BaseModel):
    id: str = Field(default_factory=_new_id)
    type: VocabularyIssueType
    text: str
    occurrences: int
    example: str
    suggestions: list[str] = Field(default_factory=list)
    explanation: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class VocabularyAnalysis(BaseModel):
    session_id: str
    provider: str
    created_at: datetime = Field(default_factory=_now)
    words_analyzed: int
    unique_words: int
    lexical_diversity: float
    vocabulary_score: int = Field(ge=0, le=100)
    issues: list[VocabularyIssue] = Field(default_factory=list)

    @computed_field
    @property
    def issue_count(self) -> int:
        return len(self.issues)


class FluencyFindingType(str, Enum):
    FILLER = "filler"
    LONG_PAUSE = "long_pause"
    REPETITION = "repetition"
    RESTART = "restart"


class FluencyFinding(BaseModel):
    id: str = Field(default_factory=_new_id)
    type: FluencyFindingType
    text: str
    occurrences: int
    detail: str = ""


class FluencyAnalysis(BaseModel):
    """How the user spoke, measured from audio timings rather than judged.

    `fluency_score` is None when the conversation contains no timed speech -
    a text-only session cannot be scored for fluency, and guessing would be
    worse than saying so.
    """

    session_id: str
    created_at: datetime = Field(default_factory=_now)

    timed_words: int
    analyzed_seconds: float
    speaking_rate_wpm: float
    articulation_rate_wpm: float

    pause_count: int
    long_pause_count: int
    total_pause_seconds: float

    filler_count: int
    repetition_count: int
    restart_count: int

    fluency_score: int | None = Field(default=None, ge=0, le=100)
    note: str = ""
    findings: list[FluencyFinding] = Field(default_factory=list)


class PronunciationSample(BaseModel):
    """One spoken turn handed to a pronunciation provider."""

    turn_id: str
    transcript: str
    audio: bytes


class PhonemeSubstitution(BaseModel):
    """One place the speaker produced a different sound from the expected one."""

    expected: str
    detected: str
    word: str
    turn_id: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class PronunciationIssue(BaseModel):
    """A substitution that recurred often enough to be worth reporting."""

    id: str = Field(default_factory=_new_id)
    expected_phoneme: str
    detected_phoneme: str
    occurrences: int
    confidence: float = Field(ge=0.0, le=1.0)
    affected_words: list[str] = Field(default_factory=list)
    practice_words: list[str] = Field(default_factory=list)
    explanation: str = ""


class PronunciationAnalysis(BaseModel):
    """Phoneme-level pronunciation findings.

    `pronunciation_score` is None when there was no spoken audio to analyse.
    """

    session_id: str
    provider: str
    created_at: datetime = Field(default_factory=_now)

    analyzed_seconds: float = 0.0
    words_analyzed: int = 0
    phonemes_analyzed: int = 0
    substitutions_found: int = 0

    pronunciation_score: int | None = Field(default=None, ge=0, le=100)
    note: str = ""
    issues: list[PronunciationIssue] = Field(default_factory=list)

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
