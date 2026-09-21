"""Generate a sample user-audio file to test the API with.

There is no frontend and no microphone capture in this backend, so this script
synthesizes a spoken utterance using the configured TTS provider and saves it
as samples/user_turn.wav. That file is what you POST to the turns endpoint.

The sentence deliberately contains a tense error ("I go ... yesterday") and a
repeated phrase ("very good"), which later analysis phases will need to find.

    uv run python scripts/make_sample.py
    uv run python scripts/make_sample.py --text "Custom sentence." --out samples/x.wav
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.providers.registry import ProviderRegistry  # noqa: E402

DEFAULT_TEXT = (
    "Hello, I go to college yesterday and it was very good. "
    "The teacher explain the lesson very good, so I am thinking about it."
)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--out", default="samples/user_turn.wav")
    args = parser.parse_args()

    settings = get_settings()
    registry = ProviderRegistry(settings)

    print(f"TTS provider: {settings.tts_provider}")
    if settings.tts_provider == "groq":
        print(f"  model: {settings.groq_tts_model}")
        print(f"  voice: {settings.groq_tts_voice}")

    try:
        tts = registry.text_to_speech()
        speech = await tts.synthesize(args.text)
    except AppError as exc:
        print(f"\nFAILED [{exc.code}] {exc.message}", file=sys.stderr)
        if exc.details:
            print(f"  details: {exc.details}", file=sys.stderr)
        return 1
    finally:
        await registry.close()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(speech.audio)

    print(f"\nWrote {out} ({len(speech.audio):,} bytes, {speech.format})")
    print(f'Text: "{args.text}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
