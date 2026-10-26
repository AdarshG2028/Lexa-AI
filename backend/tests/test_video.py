"""Uploading a video and turning it into an ordinary analysable session."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from app.audio.processing import validate_video_upload
from app.core.errors import (
    InvalidVideoError,
    UnsupportedVideoFormatError,
    VideoTooLargeError,
)
from app.providers.mock.stt import MOCK_TRANSCRIPT


def make_video(seconds: float = 2.0) -> bytes:
    """A real MP4 with both a picture and an audio track.

    The mock STT does not inspect speech, so a tone is enough; the point is
    that ffmpeg has to demux a genuine container rather than a renamed WAV.
    """
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "clip.mp4"
        result = subprocess.run(
            [
                "ffmpeg", "-nostdin", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"color=c=black:s=320x240:d={seconds}",
                "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                "-shortest",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                str(target),
            ],
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr.decode()[:500]
        return target.read_bytes()


def make_video_without_audio(seconds: float = 1.0) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "silent.mp4"
        result = subprocess.run(
            [
                "ffmpeg", "-nostdin", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"color=c=black:s=320x240:d={seconds}",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                str(target),
            ],
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr.decode()[:500]
        return target.read_bytes()


def test_validate_video_upload_accepts_known_extensions():
    assert validate_video_upload("clip.MP4", 1000, 5000) == ".mp4"
    assert validate_video_upload("clip.mov", 1000, 5000) == ".mov"
    assert validate_video_upload("clip.webm", None, 5000) == ".webm"


def test_validate_video_upload_rejects_unknown_extension():
    with pytest.raises(UnsupportedVideoFormatError):
        validate_video_upload("clip.txt", 1000, 5000)


def test_validate_video_upload_rejects_oversized_file():
    with pytest.raises(VideoTooLargeError):
        validate_video_upload("clip.mp4", 9000, 5000)


def test_validate_video_upload_rejects_empty_file():
    with pytest.raises(InvalidVideoError):
        validate_video_upload("clip.mp4", 0, 5000)


async def test_upload_limits_are_reported(client):
    body = (await client.get("/api/v1/videos/limits")).json()

    assert body["max_seconds"] == 60
    assert body["max_bytes"] > 0
    assert ".mp4" in body["formats"]
    assert ".mov" in body["formats"]


async def test_a_video_becomes_a_finished_session_with_word_timings(client):
    response = await client.post(
        "/api/v1/videos/transcribe",
        files={"file": ("clip.mp4", make_video(2.0), "video/mp4")},
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["transcript"] == MOCK_TRANSCRIPT
    assert body["word_count"] > 0
    assert 1.5 < body["duration_seconds"] < 2.5
    assert set(body["timings_ms"]) == {"normalize", "stt", "total"}

    session = (await client.get(f"/api/v1/sessions/{body['session_id']}")).json()
    assert session["mode"] == "video_coach"
    assert session["status"] == "completed"
    assert len(session["turns"]) == 1
    assert session["turns"][0]["transcript"] == MOCK_TRANSCRIPT
    assert len(session["turns"][0]["words"]) > 0
    assert session["turns"][0]["user_audio"]["duration_seconds"] > 0


async def test_the_regular_english_analyses_run_on_a_video_session(client):
    session_id = (
        await client.post(
            "/api/v1/videos/transcribe",
            files={"file": ("clip.mp4", make_video(2.0), "video/mp4")},
        )
    ).json()["session_id"]

    for kind in ("grammar", "vocabulary", "fluency"):
        response = await client.post(
            f"/api/v1/sessions/{session_id}/analysis/{kind}"
        )
        assert response.status_code == 200, response.text

    fluency = (
        await client.get(f"/api/v1/sessions/{session_id}/analysis/fluency")
    ).json()
    assert fluency["timed_words"] > 0
    assert fluency["fluency_score"] is not None


async def test_a_video_longer_than_the_limit_is_refused(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_audio_seconds", 1.0)

    response = await client.post(
        "/api/v1/videos/transcribe",
        files={"file": ("clip.mp4", make_video(2.0), "video/mp4")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "VIDEO_TOO_LONG"


async def test_a_video_without_an_audio_track_is_refused(client):
    response = await client.post(
        "/api/v1/videos/transcribe",
        files={"file": ("clip.mp4", make_video_without_audio(), "video/mp4")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_VIDEO"


async def test_a_non_video_extension_is_refused_before_upload(client):
    response = await client.post(
        "/api/v1/videos/transcribe",
        files={"file": ("notes.txt", b"not a video", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_VIDEO_FORMAT"
