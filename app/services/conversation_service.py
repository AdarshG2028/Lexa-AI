import logging
import time
from datetime import datetime, timezone

from app.audio.processing import normalize_to_wav, validate_upload
from app.config import Settings
from app.conversation.history import build_messages
from app.conversation.prompts import SYSTEM_PROMPT
from app.conversation.transcript import Transcript, build_transcript
from app.core.errors import (
    InvalidAudioError,
    SessionExpiredError,
    SessionNotActiveError,
    SessionNotFoundError,
    TurnNotFoundError,
)
from app.models import (
    AudioRef,
    Session,
    SessionStatus,
    Speaker,
    Turn,
    TurnResult,
)
from app.providers.base import LLMProvider, SpeechToTextProvider, TextToSpeechProvider
from app.sessions.repository import SessionRepository
from app.storage.base import AudioStorage

logger = logging.getLogger(__name__)


class ConversationService:
    """Orchestrates one conversational turn: audio in, audio out.

    The model is shown a trimmed window of the session's earlier exchanges on
    every turn, so it can refer back to what the user said before.
    """

    def __init__(
        self,
        stt: SpeechToTextProvider,
        llm: LLMProvider,
        tts: TextToSpeechProvider,
        sessions: SessionRepository,
        storage: AudioStorage,
        settings: Settings,
    ) -> None:
        self._stt = stt
        self._llm = llm
        self._tts = tts
        self._sessions = sessions
        self._storage = storage
        self._settings = settings

    async def start_session(self, user_id: str | None = None) -> Session:
        return await self._sessions.create(Session(user_id=user_id))

    async def get_session(self, session_id: str) -> Session:
        """Reads a session in any state. Retrieval of a finished or expired
        conversation stays available; only adding turns is restricted."""
        session = await self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id=session_id)
        return session

    async def get_active_session(self, session_id: str) -> Session:
        """The session a new turn may be added to, or an explanatory error."""
        session = await self.get_session(session_id)

        if session.status is SessionStatus.COMPLETED:
            raise SessionNotActiveError(session_id=session_id)

        idle = session.idle_seconds()
        timeout = self._settings.session_idle_timeout_minutes * 60
        if session.status is SessionStatus.EXPIRED or idle > timeout:
            if session.status is not SessionStatus.EXPIRED:
                session.status = SessionStatus.EXPIRED
                session.ended_at = session.last_activity_at
                await self._sessions.save(session)
                logger.info("Session %s expired after %.0fs idle.", session_id, idle)
            raise SessionExpiredError(
                session_id=session_id, idle_seconds=round(idle),
            )

        return session

    async def handle_audio_turn(
        self, session_id: str, audio: bytes, filename: str, mime_type: str
    ) -> TurnResult:
        session = await self.get_active_session(session_id)

        extension = validate_upload(filename, len(audio), self._settings.max_upload_bytes)
        wav_bytes, duration = normalize_to_wav(
            audio, extension, self._settings.max_audio_seconds
        )

        turn = Turn(index=len(session.turns), speaker=Speaker.USER, transcript="")

        user_key = f"{session.id}/{turn.id}-user.wav"
        await self._storage.save(user_key, wav_bytes)
        turn.user_audio = AudioRef(
            key=user_key,
            format="wav",
            duration_seconds=duration,
            size_bytes=len(wav_bytes),
        )

        started = time.perf_counter()
        transcription = await self._stt.transcribe(
            wav_bytes, f"{turn.id}.wav", "audio/wav"
        )
        stt_ms = _elapsed_ms(started)

        if not transcription.text:
            raise InvalidAudioError(
                "No speech was detected in the audio. Try speaking louder or longer."
            )
        turn.transcript = transcription.text

        return await self._complete_turn(session, turn, extra_timings={"stt": stt_ms})

    async def handle_text_turn(self, session_id: str, text: str) -> TurnResult:
        """Text in, voice out. Skips STT so the LLM and TTS legs can be
        exercised without a microphone or an audio file."""
        session = await self.get_active_session(session_id)

        if not text or not text.strip():
            raise InvalidAudioError("The message text is empty.")

        turn = Turn(
            index=len(session.turns), speaker=Speaker.USER, transcript=text.strip()
        )
        return await self._complete_turn(session, turn, extra_timings={"stt": 0})

    async def _complete_turn(
        self, session: Session, turn: Turn, extra_timings: dict[str, int]
    ) -> TurnResult:
        messages = build_messages(
            session,
            turn.transcript,
            system_prompt=SYSTEM_PROMPT,
            max_turns=self._settings.conversation_history_turns,
            max_chars=self._settings.conversation_history_max_chars,
        )

        started = time.perf_counter()
        reply = await self._llm.reply(messages)
        llm_ms = _elapsed_ms(started)
        turn.assistant_response = reply.text

        started = time.perf_counter()
        speech = await self._tts.synthesize(reply.text)
        tts_ms = _elapsed_ms(started)

        reply_key = f"{session.id}/{turn.id}-assistant.{speech.format}"
        await self._storage.save(reply_key, speech.audio)
        turn.assistant_audio = AudioRef(
            key=reply_key, format=speech.format, size_bytes=len(speech.audio)
        )

        session.turns.append(turn)
        session.last_activity_at = datetime.now(timezone.utc)
        await self._sessions.save(session)

        timings = {**extra_timings, "llm": llm_ms, "tts": tts_ms}
        timings["total"] = sum(timings.values())

        return TurnResult(
            session_id=session.id,
            turn_id=turn.id,
            transcript=turn.transcript,
            reply_text=reply.text,
            audio_url=f"/api/v1/sessions/{session.id}/turns/{turn.id}/audio",
            tts_provider=speech.provider,
            history_messages=len(messages),
            timings_ms=timings,
        )

    async def get_transcript(self, session_id: str) -> Transcript:
        """The complete conversation, in speaking order. Available at any
        point, not only once the session has ended."""
        return build_transcript(await self.get_session(session_id))

    async def get_turn_audio(
        self, session_id: str, turn_id: str, speaker: Speaker = Speaker.ASSISTANT
    ) -> tuple[bytes, str]:
        session = await self.get_session(session_id)
        turn = next((t for t in session.turns if t.id == turn_id), None)
        if turn is None:
            raise TurnNotFoundError(session_id=session_id, turn_id=turn_id)

        audio = turn.user_audio if speaker is Speaker.USER else turn.assistant_audio
        if audio is None:
            raise TurnNotFoundError(
                f"That turn has no {speaker.value} audio.",
                session_id=session_id, turn_id=turn_id,
            )
        return await self._storage.load(audio.key), audio.format

    async def end_session(self, session_id: str) -> Session:
        """Ending a conversation is idempotent: ending it twice is not an error."""
        session = await self.get_session(session_id)
        if session.status is SessionStatus.ACTIVE:
            session.status = SessionStatus.COMPLETED
            session.ended_at = datetime.now(timezone.utc)
            await self._sessions.save(session)
        return session


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
