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
