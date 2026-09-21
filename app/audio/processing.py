import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.errors import (
    AudioTooLargeError,
    ConfigError,
    InvalidAudioError,
    UnsupportedAudioFormatError,
)

SUPPORTED_EXTENSIONS = {
    ".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".ogg", ".wav", ".webm",
}

TARGET_SAMPLE_RATE = 16000


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def require_ffmpeg() -> None:
    if not ffmpeg_available():
        raise ConfigError(
            "ffmpeg and ffprobe must be installed and on PATH. "
            "Install from https://ffmpeg.org/download.html"
        )


def validate_upload(filename: str, size_bytes: int, max_bytes: int) -> str:
    """Check the filename extension and size. Returns the normalized extension."""
    if size_bytes == 0:
        raise InvalidAudioError("The uploaded file is empty.")
    if size_bytes > max_bytes:
        raise AudioTooLargeError(
            f"The upload is {size_bytes} bytes; the limit is {max_bytes} bytes.",
            limit_bytes=max_bytes,
        )

    extension = Path(filename or "").suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedAudioFormatError(
            f"'{extension or filename}' is not a supported audio format.",
            supported=sorted(SUPPORTED_EXTENSIONS),
        )
    return extension


def repair_wav_header(data: bytes) -> bytes:
    """Rewrite placeholder RIFF/data chunk sizes with the real byte counts.

    Streaming TTS endpoints emit WAV headers with 0xFFFFFFFF size fields
    because the length is unknown when the header is sent. Media players cope,
    but strict parsers report a nonsense duration and seeking breaks, so the
    sizes are corrected once the full body has arrived.
    """
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return data

    fixed = bytearray(data)
    fixed[4:8] = (len(data) - 8).to_bytes(4, "little")

    offset = 12
    while offset + 8 <= len(fixed):
        chunk_id = bytes(fixed[offset:offset + 4])
        declared = int.from_bytes(fixed[offset + 4:offset + 8], "little")
        if chunk_id == b"data":
            fixed[offset + 4:offset + 8] = (
                len(fixed) - offset - 8
            ).to_bytes(4, "little")
            break
        if declared == 0 or declared > len(fixed):
            break
        offset += 8 + declared + (declared % 2)

    return bytes(fixed)


def probe_duration(path: Path) -> float | None:
    """Read the audio duration with ffprobe.

    Raises InvalidAudioError if the file is not decodable audio, which is how a
    mislabelled upload is caught. Returns None when the stream decodes but the
    container declares no duration: a browser's MediaRecorder streams its
    output and never seeks back to patch the header, so every microphone
    recording arrives in exactly that state.
    """
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "format=duration:stream=codec_type",
            "-of", "json",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise InvalidAudioError("The file could not be decoded as audio.")

    try:
        payload = json.loads(result.stdout)
    except ValueError as exc:
        raise InvalidAudioError("The file could not be decoded as audio.") from exc

    streams = payload.get("streams", [])
    if not any(s.get("codec_type") == "audio" for s in streams):
        raise InvalidAudioError("The file contains no audio stream.")

    try:
        return float(payload["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        return None


def normalize_to_wav(audio: bytes, extension: str, max_seconds: float) -> tuple[bytes, float]:
    """Convert any supported upload to 16 kHz mono 16-bit WAV.

    Every later analysis phase (fluency timing, phoneme recognition) expects a
    single consistent audio format, so normalization happens on ingest.
    Returns the WAV bytes and the source duration in seconds.
    """
    require_ffmpeg()

    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / f"input{extension}"
        target = Path(tmp) / "output.wav"
        source.write_bytes(audio)

        duration = probe_duration(source)
        if duration is not None:
            _enforce_limit(duration, max_seconds)

        result = subprocess.run(
            [
                "ffmpeg", "-nostdin", "-y",
                "-i", str(source),
                "-ac", "1",
                "-ar", str(TARGET_SAMPLE_RATE),
                "-c:a", "pcm_s16le",
                str(target),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not target.exists():
            raise InvalidAudioError("The audio could not be converted for processing.")

        if duration is None:
            # The upload declared no length, so it is measured from the
            # converted file, which always carries a complete header. The
            # length limit is enforced here instead of before conversion; the
            # upload size cap already bounds how much work that can be.
            duration = probe_duration(target)
            if duration is None:
                raise InvalidAudioError(
                    "The audio duration could not be determined."
                )
            _enforce_limit(duration, max_seconds)

        return target.read_bytes(), duration


def _enforce_limit(duration: float, max_seconds: float) -> None:
    if duration > max_seconds:
        raise AudioTooLargeError(
            f"The audio is {duration:.1f}s long; the limit is {max_seconds:.0f}s.",
            limit_seconds=max_seconds,
        )
