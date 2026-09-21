"""Phoneme utilities shared by every pronunciation provider.

Deliberately free of torch and transformers so the conversation API, which
never loads a model, can still import the analysis package.
"""

from dataclasses import dataclass

# CMUdict (what g2p_en returns) uses ARPAbet; the wav2vec2 phoneme model
# emits IPA. Comparing them requires one common alphabet, and IPA is the one
# a learner is more likely to meet in a dictionary.
ARPABET_TO_IPA = {
    "AA": "ɑː", "AE": "æ", "AH": "ʌ", "AO": "ɔː", "AW": "aʊ", "AY": "aɪ",
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "EH": "ɛ", "ER": "ɚ",
    "EY": "eɪ", "F": "f", "G": "ɡ", "HH": "h", "IH": "ɪ", "IY": "iː",
    "JH": "dʒ", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ",
    "OW": "oʊ", "OY": "ɔɪ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ",
    "T": "t", "TH": "θ", "UH": "ʊ", "UW": "uː", "V": "v", "W": "w",
    "Y": "j", "Z": "z", "ZH": "ʒ",
}

# Sounds English learners most often substitute, with words to drill them.
PRACTICE_WORDS = {
    "θ": ["think", "three", "thank", "path", "birthday"],
    "ð": ["this", "there", "mother", "weather", "breathe"],
    "v": ["very", "voice", "seven", "love", "believe"],
    "w": ["water", "week", "away", "swim", "world"],
    "ɹ": ["red", "around", "very", "story", "sorry"],
    "l": ["light", "yellow", "believe", "call", "family"],
    "z": ["zoo", "busy", "please", "because", "eyes"],
    "s": ["see", "class", "person", "recent", "sister"],
    "ʃ": ["she", "should", "nation", "fashion", "finish"],
    "ʒ": ["measure", "usual", "vision", "decision"],
    "tʃ": ["church", "teacher", "question", "watch"],
    "dʒ": ["job", "just", "manage", "bridge", "college"],
    "ŋ": ["sing", "thing", "morning", "long", "bring"],
    "æ": ["cat", "back", "happy", "family", "answer"],
    "ɛ": ["bed", "said", "many", "ready", "friend"],
    "ɪ": ["sit", "big", "listen", "minute", "women"],
    "iː": ["see", "eat", "people", "believe", "these"],
    "ʊ": ["book", "good", "would", "put", "look"],
    "uː": ["food", "two", "school", "through", "move"],
    "ɔː": ["all", "walk", "bought", "morning", "important"],
    "ɑː": ["car", "father", "start", "heart", "market"],
    "ʌ": ["cut", "some", "money", "country", "enough"],
    "ɚ": ["her", "work", "first", "person", "world"],
    "eɪ": ["day", "make", "wait", "say", "later"],
    "oʊ": ["go", "know", "phone", "over", "most"],
    "aɪ": ["time", "my", "right", "night", "why"],
    "aʊ": ["now", "how", "about", "found", "house"],
}


# The dictionary and the acoustic model do not use identical IPA. CMUdict
# says /ʌ/ where the model hears /ɐ/, /ɚ/ where it hears /ɜː/, and marks vowel
# length that the model omits. Treating those as errors would tell a learner
# they mispronounced a word they said perfectly, so both sides are folded into
# one comparison alphabet first.
EQUIVALENT = {
    "ɐ": "ʌ", "ə": "ʌ",
    "ɜː": "ɚ", "ɝ": "ɚ", "ɹ̩": "ɚ", "ɐ˞": "ɚ",
    "i": "iː", "ɪ̈": "ɪ",
    "u": "uː", "ʊ̈": "ʊ",
    "ɔ": "ɔː", "ɔːɹ": "ɔː", "oː": "ɔː",
    "ɑ": "ɑː", "ɑːɹ": "ɑː", "ɒ": "ɑː",
    "e": "ɛ", "ɛɹ": "ɛ", "eː": "eɪ",
    "ɡ": "ɡ", "g": "ɡ",
    "r": "ɹ", "ɾ": "ɹ", "ɪɹ": "ɪ", "ʊɹ": "ʊ",
    "o": "oʊ", "əʊ": "oʊ",
    "n̩": "n", "l̩": "l", "m̩": "m",
    "ʔ": "t",
}


# Vowels in unstressed function words are routinely reduced in connected
# speech - nobody says "and" with the vowel the dictionary gives it. Judging
# those vowels against the citation form invents errors. Consonants are not
# reduced the same way, so they are still assessed even in these words.
FUNCTION_WORDS = {
    "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "at", "for",
    "is", "are", "was", "were", "be", "been", "am", "do", "does", "did",
    "have", "has", "had", "will", "would", "can", "could", "should", "as",
    "from", "with", "by", "that", "than", "then", "so", "if", "it", "its",
}

VOWELS = {
    "ɑː", "æ", "ʌ", "ɔː", "aʊ", "aɪ", "ɛ", "ɚ", "eɪ", "ɪ", "iː", "oʊ",
    "ɔɪ", "ʊ", "uː", "ə", "ɐ", "ɜː",
}


def is_vowel(phoneme: str) -> bool:
    return normalize(phoneme) in VOWELS or phoneme in VOWELS


def is_reduced_vowel_context(word: str | None, expected: str) -> bool:
    """True when this phoneme should not be judged at all."""
    return bool(word) and word.lower() in FUNCTION_WORDS and is_vowel(expected)


def normalize(phoneme: str) -> str:
    """Folds notational variants together so only real differences remain."""
    return EQUIVALENT.get(phoneme, phoneme)


def same_sound(a: str, b: str) -> bool:
    return normalize(a) == normalize(b)


def arpabet_to_ipa(phone: str) -> str | None:
    """Converts one ARPAbet phone, dropping the stress digit CMUdict adds."""
    stripped = phone.rstrip("0123456789").upper()
    return ARPABET_TO_IPA.get(stripped)


@dataclass
class ExpectedPhoneme:
    """One phoneme the speaker was trying to produce, and its word."""

    phoneme: str
    word: str


def expected_phonemes(text: str) -> list[ExpectedPhoneme]:
    """What the words in `text` should sound like.

    Imports g2p_en lazily: it pulls in nltk, which is part of the optional
    pronunciation stack rather than a dependency of the conversation API.
    """
    from app.analysis.g2p import grapheme_to_phoneme

    return grapheme_to_phoneme(text)


@dataclass
class Alignment:
    """One position in the comparison of expected against detected speech."""

    expected: str | None
    detected: str | None
    word: str | None

    @property
    def is_substitution(self) -> bool:
        return (
            self.expected is not None
            and self.detected is not None
            and not same_sound(self.expected, self.detected)
        )


def align(
    expected: list[ExpectedPhoneme], detected: list[str]
) -> list[Alignment]:
    """Needleman-Wunsch alignment of the two phoneme sequences.

    A global alignment is used rather than a naive index-by-index comparison
    because a learner who inserts or drops a sound would otherwise throw every
    later phoneme out of step and produce a cascade of false errors.
    """
    n, m = len(expected), len(detected)
    if n == 0 or m == 0:
        return (
            [Alignment(e.phoneme, None, e.word) for e in expected]
            + [Alignment(None, d, None) for d in detected]
        )

    # cost[i][j] = cheapest edit distance between expected[:i] and detected[:j]
    cost = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        cost[i][0] = i
    for j in range(1, m + 1):
        cost[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            substitution = cost[i - 1][j - 1] + (
                0 if same_sound(expected[i - 1].phoneme, detected[j - 1]) else 1
            )
            cost[i][j] = min(substitution, cost[i - 1][j] + 1, cost[i][j - 1] + 1)

    aligned: list[Alignment] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            same = same_sound(expected[i - 1].phoneme, detected[j - 1])
            if cost[i][j] == cost[i - 1][j - 1] + (0 if same else 1):
                aligned.append(
                    Alignment(expected[i - 1].phoneme, detected[j - 1],
                              expected[i - 1].word)
                )
                i, j = i - 1, j - 1
                continue
        if i > 0 and cost[i][j] == cost[i - 1][j] + 1:
            aligned.append(Alignment(expected[i - 1].phoneme, None,
                                     expected[i - 1].word))
            i -= 1
            continue
        aligned.append(Alignment(None, detected[j - 1], None))
        j -= 1

    aligned.reverse()
    return aligned


def practice_words(phoneme: str) -> list[str]:
    return PRACTICE_WORDS.get(phoneme, [])
