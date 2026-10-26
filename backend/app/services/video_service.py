import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from app.audio.processing import normalize_path_to_wav
from app.config import Settings
from app.core.errors import (
    AudioTooLargeError,
    InvalidAudioError,
    InvalidVideoError,
    VideoTooLongError,
)
from app.models import (
    AudioRef,
    Session,
    SessionMode,
    SessionStatus,
    Speaker,
    Turn,
    VideoTranscriptionResult,
)
from app.providers.base import SpeechToTextProvider
from app.sessions.repository import SessionRepository
from app.storage.base import AudioStorage

logger = logging.getLogger(__name__)


class VideoService:
    """Turns an uploaded English video into a finished, analysable session.

    The video itself is not kept: only the normalised audio, the transcript
    and the word timings are stored. The regular grammar, vocabulary and
    fluency services already know how to read a session with a user turn, so
    this service's whole job is to produce one without an assistant reply.
    """

    def __init__(
        self,
        stt: SpeechToTextProvider,
        sessions: SessionRepository,
        storage: AudioStorage,
        settings: Settings,
    ) -> None:
        self._stt = stt
        self._sessions = sessions
        self._storage = storage
        self._settings = settings

    async def transcribe_video(self, source: Path) -> VideoTranscriptionResult:
        started = time.perf_counter()
        try:
            wav_bytes, duration = await asyncio.to_thread(
                normalize_path_to_wav, source, self._settings.max_audio_seconds
            )
        except AudioTooLargeError as exc:
            limit = self._settings.max_audio_seconds
            raise VideoTooLongError(
                f"The video is longer than {limit:.0f} seconds. "
                "Trim it and upload it again.",
                limit_seconds=limit,
            ) from exc
        except InvalidAudioError as exc:
            raise InvalidVideoError(
                "The video has no readable audio track. Upload one with "
                "spoken English in it."
            ) from exc
        normalize_ms = _elapsed_ms(started)

        turn = Turn(index=0, speaker=Speaker.USER, transcript="")
        started = time.perf_counter()
        transcription = await self._stt.transcribe(
            wav_bytes,
            f"{turn.id}.wav",
            "audio/wav",
            # Pinned rather than auto-detected: this feature is specifically
            # for English speech, and Whisper's guess can turn English audio
            # into another language's phonetics.
            language="en",
        )
        stt_ms = _elapsed_ms(started)

        text = transcription.text.strip()
        if not text:
            raise InvalidVideoError(
                "No speech was detected in the video. Make sure it has clear "
                "spoken English, then try again."
            )

        now = datetime.now(timezone.utc)
        session = Session(
            status=SessionStatus.COMPLETED,
            mode=SessionMode.VIDEO_COACH,
            started_at=now,
            last_activity_at=now,
            ended_at=now,
        )
        turn.transcript = text
        turn.words = transcription.words

        user_key = f"{session.id}/{turn.id}-user.wav"
        await self._storage.save(user_key, wav_bytes)
        turn.user_audio = AudioRef(
            key=user_key,
            format="wav",
            duration_seconds=duration,
            size_bytes=len(wav_bytes),
        )
        session.turns.append(turn)
        await self._sessions.create(session)

        timings = {"normalize": normalize_ms, "stt": stt_ms}
        timings["total"] = sum(timings.values())
        logger.info(
            "Video transcribed into session %s: %.1fs, %d words",
            session.id,
            duration,
            len(transcription.words),
        )
        return VideoTranscriptionResult(
            session_id=session.id,
            turn_id=turn.id,
            transcript=text,
            language=transcription.language or "en",
            duration_seconds=duration,
            word_count=len(transcription.words) or len(text.split()),
            timings_ms=timings,
        )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
