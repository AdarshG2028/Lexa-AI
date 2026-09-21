import pytest

from app.audio.processing import (
    TARGET_SAMPLE_RATE,
    normalize_to_wav,
    repair_wav_header,
    validate_upload,
)
from app.core.errors import (
    AudioTooLargeError,
    InvalidAudioError,
    UnsupportedAudioFormatError,
)
from tests.conftest import make_wav

import io
import wave


def test_validate_upload_accepts_known_extensions():
    assert validate_upload("clip.WAV", 1000, 5000) == ".wav"
    assert validate_upload("clip.m4a", 1000, 5000) == ".m4a"


def test_validate_upload_rejects_empty_file():
    with pytest.raises(InvalidAudioError):
        validate_upload("clip.wav", 0, 5000)


def test_validate_upload_rejects_oversized_file():
    with pytest.raises(AudioTooLargeError):
        validate_upload("clip.wav", 9000, 5000)


def test_validate_upload_rejects_unknown_extension():
    with pytest.raises(UnsupportedAudioFormatError):
        validate_upload("clip.txt", 1000, 5000)


def test_normalize_downsamples_to_16k_mono():
    source = make_wav(seconds=1.0, sample_rate=44100)
    normalized, duration = normalize_to_wav(source, ".wav", max_seconds=60)

    with wave.open(io.BytesIO(normalized), "rb") as handle:
        assert handle.getframerate() == TARGET_SAMPLE_RATE
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
    assert 0.9 < duration < 1.1


def test_normalize_rejects_bytes_that_are_not_audio():
    with pytest.raises(InvalidAudioError):
        normalize_to_wav(b"definitely not a wav file", ".wav", max_seconds=60)


def test_normalize_rejects_audio_longer_than_the_limit():
    source = make_wav(seconds=3.0)
    with pytest.raises(AudioTooLargeError):
        normalize_to_wav(source, ".wav", max_seconds=1.0)


def test_repair_wav_header_fixes_streaming_placeholder_sizes():
    """Streaming TTS endpoints send 0xFFFFFFFF sizes because the length is not
    known when the header is written."""
    good = make_wav(seconds=0.5)
    broken = bytearray(good)
    broken[4:8] = b"\xff\xff\xff\xff"
    data_at = bytes(broken).find(b"data")
    broken[data_at + 4:data_at + 8] = b"\xff\xff\xff\xff"

    repaired = repair_wav_header(bytes(broken))

    with wave.open(io.BytesIO(repaired), "rb") as handle:
        assert handle.getnframes() == 8000
        assert abs(handle.getnframes() / handle.getframerate() - 0.5) < 0.01


def test_repair_wav_header_leaves_a_valid_file_unchanged():
    good = make_wav(seconds=0.5)
    assert repair_wav_header(good) == good


def test_repair_wav_header_ignores_non_wav_bytes():
    assert repair_wav_header(b"not a wav") == b"not a wav"


def test_streamed_audio_without_a_declared_duration_is_accepted():
    """What a browser's MediaRecorder produces: the encoder streams its output
    and never seeks back to write the duration into the header. Rejecting that
    would reject every microphone recording."""
    import subprocess

    source = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:a", "libopus", "-f", "webm", "pipe:1"],
        capture_output=True,
    )
    assert source.returncode == 0, source.stderr.decode()[:400]

    wav, duration = normalize_to_wav(source.stdout, ".webm", max_seconds=60)

    assert wav[:4] == b"RIFF"
    assert 1.5 < duration < 2.5


async def test_a_slow_conversion_does_not_freeze_the_server(client, monkeypatch):
    """ffmpeg is a blocking subprocess. If it ran on the event loop, every other
    request - the host's health check included - would wait for it."""
    import asyncio
    import time

    def slow_conversion(audio, extension, max_seconds):
        time.sleep(0.6)
        return make_wav(1.0), 1.0

    monkeypatch.setattr(
        "app.services.conversation_service.normalize_to_wav", slow_conversion
    )
    session_id = (await client.post("/api/v1/sessions")).json()["id"]

    started = time.perf_counter()
    turn = asyncio.create_task(
        client.post(
            f"/api/v1/sessions/{session_id}/turns",
            files={"file": ("speech.wav", make_wav(1.0), "audio/wav")},
        )
    )
    await asyncio.sleep(0.1)
    health = await client.get("/health")
    elapsed = time.perf_counter() - started
    await turn

    # Timed from before the conversion began: if it blocks the event loop, even
    # a 0.1 s sleep cannot resume until the 0.6 s conversion has finished.
    assert health.status_code == 200
    assert elapsed < 0.4
