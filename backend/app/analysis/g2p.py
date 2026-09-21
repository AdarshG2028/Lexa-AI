"""Grapheme-to-phoneme conversion.

Isolated in its own module because g2p_en pulls in nltk and its corpora,
which belong to the optional pronunciation stack.
"""

import logging
import re
from functools import lru_cache

from app.analysis.phonemes import ExpectedPhoneme, arpabet_to_ipa
from app.core.errors import ConfigError

logger = logging.getLogger(__name__)


# g2p_en downloads the corpora it knew about; newer nltk renamed the tagger,
# so the current names are fetched here as well.
NLTK_RESOURCES = [
    ("taggers/averaged_perceptron_tagger_eng", "averaged_perceptron_tagger_eng"),
    ("corpora/cmudict", "cmudict"),
]


def _ensure_nltk_data() -> None:
    import nltk

    for path, package in NLTK_RESOURCES:
        try:
            nltk.data.find(path)
        except LookupError:
            logger.info("Downloading nltk resource %s", package)
            nltk.download(package, quiet=True)


@lru_cache(maxsize=1)
def _engine():
    try:
        from g2p_en import G2p
    except ImportError as exc:
        raise ConfigError(
            "The pronunciation stack is not installed. Run: "
            "uv sync --group pronunciation"
        ) from exc

    _ensure_nltk_data()
    return G2p()


def grapheme_to_phoneme(text: str) -> list[ExpectedPhoneme]:
    """The phonemes each word of `text` should be made of.

    g2p_en returns ARPAbet with stress digits and inserts a space token
    between words, which is what lets each phoneme be tied back to the word it
    came from.
    """
    words = re.findall(r"[A-Za-z']+", text)
    if not words:
        return []

    engine = _engine()
    expected: list[ExpectedPhoneme] = []

    for word in words:
        for phone in engine(word):
            ipa = arpabet_to_ipa(phone)
            if ipa:
                expected.append(ExpectedPhoneme(phoneme=ipa, word=word.lower()))

    return expected
