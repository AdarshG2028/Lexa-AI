from datetime import datetime

from pydantic import BaseModel

from app.models import Session, SessionStatus, Speaker


class TranscriptEntry(BaseModel):
    """One utterance by one speaker, flattened out of a conversation turn."""

    index: int
    turn_id: str
    speaker: Speaker
    text: str
    timestamp: datetime
    audio_url: str | None = None
    audio_duration_seconds: float | None = None


class Transcript(BaseModel):
    session_id: str
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: float
    turn_count: int
    entries: list[TranscriptEntry]
    plain_text: str


def build_transcript(session: Session) -> Transcript:
    """Flattens a session's turns into an alternating speaker transcript.

    A stored turn holds one exchange - what the user said and how the AI
    replied. Analysis works on utterances, so each turn becomes up to two
    entries in speaking order.
    """
    entries: list[TranscriptEntry] = []

    for turn in session.turns:
        entries.append(
            TranscriptEntry(
                index=len(entries),
                turn_id=turn.id,
                speaker=Speaker.USER,
                text=turn.transcript,
                timestamp=turn.created_at,
                audio_url=(
                    f"/api/v1/sessions/{session.id}/turns/{turn.id}/audio/user"
                    if turn.user_audio
                    else None
                ),
                audio_duration_seconds=(
                    turn.user_audio.duration_seconds if turn.user_audio else None
                ),
            )
        )

        if turn.assistant_response:
            entries.append(
                TranscriptEntry(
                    index=len(entries),
                    turn_id=turn.id,
                    speaker=Speaker.ASSISTANT,
                    text=turn.assistant_response,
                    timestamp=turn.created_at,
                    audio_url=(
                        f"/api/v1/sessions/{session.id}/turns/{turn.id}/audio"
                        if turn.assistant_audio
                        else None
                    ),
                    audio_duration_seconds=(
                        turn.assistant_audio.duration_seconds
                        if turn.assistant_audio
                        else None
                    ),
                )
            )

    return Transcript(
        session_id=session.id,
        status=session.status,
        started_at=session.started_at,
        ended_at=session.ended_at,
        duration_seconds=session.duration_seconds,
        turn_count=session.turn_count,
        entries=entries,
        plain_text=to_plain_text(entries),
    )


def to_plain_text(entries: list[TranscriptEntry]) -> str:
    labels = {Speaker.USER: "You", Speaker.ASSISTANT: "AI"}
    return "\n".join(f"{labels[e.speaker]}: {e.text}" for e in entries)
