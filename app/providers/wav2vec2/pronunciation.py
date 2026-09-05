import asyncio
import io
import logging
import wave

from app.analysis.phonemes import align, expected_phonemes
from app.config import Settings
from app.core.errors import ConfigError, ProviderUnavailableError
from app.models import (
    PhonemeSubstitution,
    ProviderCheck,
    PronunciationSample,
)

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000


class Wav2Vec2PronunciationProvider:
    """Phoneme recognition with a wav2vec2 CTC model.

    The model emits IPA directly, so no espeak or phonemizer backend is needed
    at inference - the tokenizer is loaded with `do_phonemize=False`, which is
    what keeps this installable on Windows and inside a slim container.

    torch and transformers are imported lazily and the model is loaded once,
    on first use. Nothing here is imported by the conversation API.
    """

    name = "wav2vec2"

    def __init__(self, settings: Settings) -> None:
        self._model_id = settings.pronunciation_model
        self._threads = settings.pronunciation_torch_threads
        self._model = None
        self._extractor = None
        self._tokenizer = None
        self._lock = asyncio.Lock()

    def _load(self) -> None:
        try:
            import torch
            from transformers import (
                Wav2Vec2FeatureExtractor,
                Wav2Vec2ForCTC,
                Wav2Vec2PhonemeCTCTokenizer,
            )
        except ImportError as exc:
            raise ConfigError(
                "The pronunciation stack is not installed. Run: "
                "uv sync --group pronunciation"
            ) from exc

        if self._threads > 0:
            torch.set_num_threads(self._threads)

        logger.info("Loading pronunciation model %s", self._model_id)
        self._tokenizer = Wav2Vec2PhonemeCTCTokenizer.from_pretrained(
            self._model_id, do_phonemize=False
        )
        self._extractor = Wav2Vec2FeatureExtractor.from_pretrained(self._model_id)
        self._model = Wav2Vec2ForCTC.from_pretrained(self._model_id)
        self._model.eval()
        logger.info("Pronunciation model ready")

    async def _ensure_loaded(self) -> None:
        async with self._lock:
            if self._model is None:
                await asyncio.to_thread(self._load)

    async def analyze(
        self, samples: list[PronunciationSample]
    ) -> list[PhonemeSubstitution]:
        if not samples:
            return []

        await self._ensure_loaded()

        substitutions: list[PhonemeSubstitution] = []
        for sample in samples:
            try:
                found = await asyncio.to_thread(self._analyze_one, sample)
            except ConfigError:
                raise
            except Exception as exc:
                # One unreadable turn should not lose the whole analysis.
                logger.warning(
                    "Pronunciation analysis failed for turn %s: %s",
                    sample.turn_id, exc,
                )
                continue
            substitutions.extend(found)

        return substitutions

    def _analyze_one(
        self, sample: PronunciationSample
    ) -> list[PhonemeSubstitution]:
        audio = _read_wav(sample.audio)
        if audio is None or len(audio) < SAMPLE_RATE // 10:
            return []

        detected, confidences = self._recognize(audio)
        if not detected:
            return []

        expected = expected_phonemes(sample.transcript)
        if not expected:
            return []

        found: list[PhonemeSubstitution] = []
        position = 0
        for step in align(expected, detected):
            if step.detected is not None:
                confidence = confidences[position] if position < len(confidences) else 0.5
                position += 1
            else:
                confidence = 0.5

            if step.is_substitution and step.word:
                found.append(
                    PhonemeSubstitution(
                        expected=step.expected,
                        detected=step.detected,
                        word=step.word,
                        turn_id=sample.turn_id,
                        confidence=confidence,
                    )
                )
        return found

    def _recognize(self, audio) -> tuple[list[str], list[float]]:
        """Returns the phonemes heard and how confident the model was in each.

        CTC emits one label per 20 ms frame with blanks between; repeated
        labels are collapsed into a single phoneme whose confidence is the
        mean probability across the frames that produced it.
        """
        import torch

        inputs = self._extractor(
            audio, sampling_rate=SAMPLE_RATE, return_tensors="pt"
        )
        with torch.no_grad():
            logits = self._model(inputs.input_values).logits[0]

        probabilities = torch.softmax(logits, dim=-1)
        best = torch.argmax(probabilities, dim=-1)
        scores = probabilities.max(dim=-1).values

        blank = self._model.config.pad_token_id
        vocab = self._tokenizer.convert_ids_to_tokens

        phonemes: list[str] = []
        confidences: list[float] = []
        run: list[float] = []
        previous = None

        for token_id, score in zip(best.tolist(), scores.tolist()):
            if token_id != previous and previous is not None and run:
                phonemes.append(vocab([previous])[0])
                confidences.append(sum(run) / len(run))
                run = []
            if token_id != blank:
                run.append(score)
            previous = token_id if token_id != blank else None

        if previous is not None and run:
            phonemes.append(vocab([previous])[0])
            confidences.append(sum(run) / len(run))

        keep = [
            (p, c) for p, c in zip(phonemes, confidences)
            if p and p not in ("<pad>", "<s>", "</s>", "<unk>", "|")
        ]
        return [p for p, _ in keep], [c for _, c in keep]

    async def check(self) -> ProviderCheck:
        """Reports configuration without loading 1.2 GB of weights."""
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError:
            return ProviderCheck(
                provider=self.name,
                model=self._model_id,
                model_listed=False,
                note="Not installed. Run: uv sync --group pronunciation",
            )
        return ProviderCheck(
            provider=self.name,
            model=self._model_id,
            note="Weights load on first use; the first analysis is slower.",
        )


def _read_wav(data: bytes):
    """Reads 16 kHz mono 16-bit PCM into a float array."""
    try:
        import numpy as np
    except ImportError as exc:
        raise ConfigError(
            "The pronunciation stack is not installed. Run: "
            "uv sync --group pronunciation"
        ) from exc

    try:
        with wave.open(io.BytesIO(data), "rb") as handle:
            if handle.getframerate() != SAMPLE_RATE or handle.getnchannels() != 1:
                raise ProviderUnavailableError(
                    "Pronunciation analysis expects 16 kHz mono audio."
                )
            frames = handle.readframes(handle.getnframes())
    except wave.Error:
        return None

    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
