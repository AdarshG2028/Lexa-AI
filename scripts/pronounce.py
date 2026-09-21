"""Run pronunciation analysis on audio files, then exit.

The phoneme model needs ~1.5-2 GB of RAM. Loading it inside the long-running
API server holds that memory for the life of the process; running it here
releases it the moment the script finishes, which is what makes local testing
practical on a small machine.

    uv run python scripts/pronounce.py samples/th_mispronounced.wav
    uv run python scripts/pronounce.py a.wav b.wav c.wav        # one conversation
    uv run python scripts/pronounce.py my.wav --text "what I actually said"
    uv run python scripts/pronounce.py my.wav --min-occurrences 1 --min-distinct-words 1

Without --text the audio is transcribed first, exactly as the API does: the
transcript supplies the expected pronunciation, the audio supplies the actual.
"""

import argparse
import asyncio
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Keep model weights off the system drive unless told otherwise.
os.environ.setdefault("HF_HOME", str(Path(__file__).resolve().parent.parent / "data" / "models"))

from app.analysis.pronunciation import (  # noqa: E402
    MIN_CONFIDENCE,
    MIN_DISTINCT_WORDS,
    MIN_OCCURRENCES,
    aggregate,
    score,
)
from app.config import get_settings  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.models import PronunciationSample  # noqa: E402
from app.providers.registry import ProviderRegistry  # noqa: E402

SAMPLE_RATE = 16000


def normalize(path: Path) -> bytes:
    """Convert to the 16 kHz mono WAV the model expects.

    A temporary directory rather than a temporary file: Windows will not let
    a file be deleted while a handle to it is still open.
    """
    with tempfile.TemporaryDirectory() as workspace:
        target = Path(workspace) / "audio.wav"
        result = subprocess.run(
            ["ffmpeg", "-nostdin", "-y", "-i", str(path), "-ac", "1",
             "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(target)],
            capture_output=True,
        )
        if result.returncode != 0 or not target.exists():
            raise SystemExit(f"ffmpeg could not read {path}")
        return target.read_bytes()


def free_ram_gb() -> float | None:
    try:
        output = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
            capture_output=True, text=True, timeout=20,
        ).stdout.strip()
        return int(output) / 1024 / 1024
    except Exception:
        return None


async def run(args) -> int:
    settings = get_settings()
    registry = ProviderRegistry(settings)

    if settings.pronunciation_provider != "wav2vec2":
        print(f"PRONUNCIATION_PROVIDER is '{settings.pronunciation_provider}'. "
              "This script is for the real model; set it to wav2vec2 in .env.",
              file=sys.stderr)

    free = free_ram_gb()
    if free is not None:
        print(f"free RAM: {free:.2f} GB  (the model needs roughly 2 GB)")
        if free < 1.8:
            print("  warning: this is tight. Expect heavy swapping, or close "
                  "some applications first.\n")

    samples: list[PronunciationSample] = []
    try:
        for index, path in enumerate(args.files):
            if not path.is_file():
                print(f"no such file: {path}", file=sys.stderr)
                return 1

            audio = normalize(path)

            if args.text:
                transcript = args.text
                print(f"[{path.name}] using supplied text")
            else:
                started = time.perf_counter()
                result = await registry.speech_to_text().transcribe(
                    audio, path.name, "audio/wav"
                )
                transcript = result.text
                print(f"[{path.name}] transcribed in "
                      f"{time.perf_counter() - started:.1f}s")
                print(f"    {transcript}")

            if not transcript.strip():
                print(f"    no speech detected, skipping")
                continue

            samples.append(PronunciationSample(
                turn_id=f"file{index}", transcript=transcript, audio=audio
            ))

        if not samples:
            print("\nnothing to analyse.")
            return 1

        print(f"\nloading phoneme model ({settings.pronunciation_model})")
        print("  the first run takes 60-100s; after that it is ~1.35x realtime\n")

        started = time.perf_counter()
        substitutions = await registry.pronunciation().analyze(samples)
        elapsed = time.perf_counter() - started
    except AppError as exc:
        print(f"\nFAILED [{exc.code}] {exc.message}", file=sys.stderr)
        return 1
    finally:
        await registry.close()

    print(f"analysis took {elapsed:.1f}s")
    print(f"raw mismatches: {len(substitutions)}")

    pairs = Counter((s.expected, s.detected) for s in substitutions)
    for (expected, detected), count in pairs.most_common(10):
        print(f"    /{expected}/ -> /{detected}/   x{count}")

    issues = aggregate(
        substitutions,
        min_occurrences=args.min_occurrences,
        min_confidence=args.min_confidence,
        min_distinct_words=args.min_distinct_words,
    )
    words = sum(len(s.transcript.split()) for s in samples)

    print(f"\nthresholds: >= {args.min_occurrences} occurrences, "
          f">= {args.min_distinct_words} distinct words, "
          f">= {args.min_confidence} confidence")
    print(f"PRONUNCIATION SCORE: {score(issues, words)}/100")

    if not issues:
        print("\nNothing reported. On clearly spoken audio that is the correct "
              "outcome - the raw mismatches above are usually accent or "
              "recogniser noise rather than real errors.")
        return 0

    print(f"\nREPORTED ({len(issues)}):")
    for issue in issues:
        print(f"\n  /{issue.expected_phoneme}/ -> /{issue.detected_phoneme}/"
              f"   x{issue.occurrences}   confidence {issue.confidence:.2f}")
        print(f"     words    : {', '.join(issue.affected_words)}")
        print(f"     practise : {', '.join(issue.practice_words[:5])}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path,
                        help="Audio files, treated as turns of one conversation.")
    parser.add_argument("--text", help="Skip transcription and use this text.")
    parser.add_argument("--min-occurrences", type=int, default=MIN_OCCURRENCES)
    parser.add_argument("--min-distinct-words", type=int, default=MIN_DISTINCT_WORDS)
    parser.add_argument("--min-confidence", type=float, default=MIN_CONFIDENCE)
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
