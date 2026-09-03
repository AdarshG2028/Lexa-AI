from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import ConversationServiceDep
from app.conversation.transcript import Transcript
from app.models import Session, Speaker, TurnResult

router = APIRouter(prefix="/api/v1/sessions", tags=["conversation"])

MEDIA_TYPES = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
    "flac": "audio/flac",
}


class StartSessionRequest(BaseModel):
    user_id: str | None = None


class TextTurnRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("", status_code=201, response_model=Session)
async def start_session(
    service: ConversationServiceDep, body: StartSessionRequest | None = None
) -> Session:
    return await service.start_session(user_id=body.user_id if body else None)


@router.get("/{session_id}", response_model=Session)
async def get_session(session_id: str, service: ConversationServiceDep) -> Session:
    return await service.get_session(session_id)


@router.post("/{session_id}/turns", response_model=TurnResult)
async def create_audio_turn(
    session_id: str,
    service: ConversationServiceDep,
    file: UploadFile = File(..., description="User audio: wav, mp3, m4a, ogg, webm…"),
) -> TurnResult:
    audio = await file.read()
    return await service.handle_audio_turn(
        session_id,
        audio,
        file.filename or "audio",
        file.content_type or "application/octet-stream",
    )


@router.post("/{session_id}/turns/text", response_model=TurnResult)
async def create_text_turn(
    session_id: str, body: TextTurnRequest, service: ConversationServiceDep
) -> TurnResult:
    return await service.handle_text_turn(session_id, body.text)


@router.get("/{session_id}/turns/{turn_id}/audio")
async def get_assistant_audio(
    session_id: str, turn_id: str, service: ConversationServiceDep
) -> Response:
    data, audio_format = await service.get_turn_audio(session_id, turn_id)
    return _audio_response(data, audio_format)


@router.get("/{session_id}/turns/{turn_id}/audio/user")
async def get_user_audio(
    session_id: str, turn_id: str, service: ConversationServiceDep
) -> Response:
    """The user's own speech, normalised to 16 kHz mono WAV. The later
    fluency and pronunciation phases analyse exactly this audio."""
    data, audio_format = await service.get_turn_audio(
        session_id, turn_id, speaker=Speaker.USER
    )
    return _audio_response(data, audio_format)


@router.get("/{session_id}/transcript", response_model=Transcript)
async def get_transcript(
    session_id: str, service: ConversationServiceDep, format: str = "json"
) -> Response | Transcript:
    """The complete conversation. `format=text` returns it as plain text."""
    transcript = await service.get_transcript(session_id)
    if format == "text":
        return Response(content=transcript.plain_text, media_type="text/plain")
    return transcript


def _audio_response(data: bytes, audio_format: str) -> Response:
    return Response(
        content=data,
        media_type=MEDIA_TYPES.get(audio_format, "application/octet-stream"),
    )


@router.post("/{session_id}/end", response_model=Session)
async def end_session(session_id: str, service: ConversationServiceDep) -> Session:
    return await service.end_session(session_id)
