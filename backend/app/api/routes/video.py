import asyncio
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from app.api.deps import SettingsDep, VideoServiceDep
from app.audio.processing import SUPPORTED_VIDEO_EXTENSIONS, validate_video_upload
from app.core.errors import InvalidVideoError, VideoTooLargeError
from app.models import VideoTranscriptionResult, VideoUploadLimits

router = APIRouter(prefix="/api/v1/videos", tags=["video coaching"])


@router.get("/limits", response_model=VideoUploadLimits)
async def upload_limits(settings: SettingsDep) -> VideoUploadLimits:
    """What the frontend needs to reject an obviously unusable file before
    spending time uploading it."""
    return VideoUploadLimits(
        max_seconds=settings.max_audio_seconds,
        max_bytes=settings.max_video_upload_bytes,
        formats=sorted(SUPPORTED_VIDEO_EXTENSIONS),
    )


@router.post("/transcribe", response_model=VideoTranscriptionResult)
async def transcribe_video(
    service: VideoServiceDep,
    settings: SettingsDep,
    file: UploadFile = File(
        ...,
        description="English video: mp4, mov, m4v, webm, mkv or avi",
    ),
) -> VideoTranscriptionResult:
    """Extract the audio from an uploaded video, transcribe it, and return a
    finished session id.

    The client then runs the ordinary grammar, vocabulary and fluency
    endpoints against that session. Nothing about those analyses changes
    because the speech arrived in a video container.
    """
    filename = file.filename or "video"
    extension = validate_video_upload(
        filename, file.size, settings.max_video_upload_bytes
    )

    # Read the upload a megabyte at a time instead of `await file.read()`.
    # A five-minute video can be much larger than a single audio turn, and
    # holding one entirely in memory would allocate that much per request.
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as handle:
        target = Path(handle.name)

    try:
        size = await asyncio.to_thread(
            _copy_upload, file.file, target, settings.max_video_upload_bytes
        )
        if size == 0:
            raise InvalidVideoError("The uploaded video is empty.")
        return await service.transcribe_video(target)
    finally:
        target.unlink(missing_ok=True)
        await file.close()


def _copy_upload(source, target: Path, max_bytes: int) -> int:
    """Copy the multipart body to disk, enforcing the size limit on the bytes
    that actually arrive rather than trusting a header."""
    size = 0
    with target.open("wb") as out:
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                raise VideoTooLargeError(
                    f"The video is larger than {max_bytes // 1_000_000} MB.",
                    limit_bytes=max_bytes,
                )
            out.write(chunk)
    return size
