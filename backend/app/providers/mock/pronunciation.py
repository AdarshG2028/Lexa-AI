import re

from app.models import (
    PhonemeSubstitution,
    ProviderCheck,
    PronunciationSample,
)

# Substitutions learners of English commonly make, keyed by a spelling that
# reliably contains the target sound.
PATTERNS = [
    (r"\b(think|thing|three|thank|thursday|through|throw|birthday)\b", "θ", "t"),
    (r"\b(this|that|there|they|then|them|mother|father|weather)\b", "ð", "d"),
    (r"\b(very|voice|value|van|seven|love|believe|involve)\b", "v", "w"),
    (r"\b(zoo|zero|busy|please|because|easy|reason)\b", "z", "s"),
    (r"\b(vision|measure|usual|pleasure|decision)\b", "ʒ", "z"),
]


class MockPronunciationAnalysisProvider:
    """Offline pronunciation findings driven by spelling rather than audio.

    It cannot hear anything, so it is not a substitute for the model. What it
    gives is a deterministic, key-free way to exercise the aggregation,
    filtering and reporting that sit above the provider.
    """

    name = "mock"

    async def analyze(
        self, samples: list[PronunciationSample]
    ) -> list[PhonemeSubstitution]:
        found: list[PhonemeSubstitution] = []
        for sample in samples:
            for pattern, expected, detected in PATTERNS:
                for match in re.finditer(pattern, sample.transcript, re.IGNORECASE):
                    found.append(
                        PhonemeSubstitution(
                            expected=expected,
                            detected=detected,
                            word=match.group(0).lower(),
                            turn_id=sample.turn_id,
                            confidence=0.85,
                        )
                    )
        return found

    async def check(self) -> ProviderCheck:
        return ProviderCheck(
            provider=self.name,
            note="Spelling-based, not acoustic. For offline testing only.",
        )
