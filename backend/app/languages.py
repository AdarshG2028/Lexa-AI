from dataclasses import dataclass


@dataclass(frozen=True)
class SpokenLanguage:
    """A language a learner can speak to the app in instead of English.

    Each language is its own entry rather than a parameter of a shared
    template: the ways they go wrong differ (how much English is mixed in,
    how far speech drifts from the written form, how well recognition copes),
    and what the model is told about each should be able to differ with them.
    """

    code: str  # ISO 639-1; also the code speech recognition is pinned to
    name: str
    native_name: str
    script: str
    # What the language model is told about how this language is spoken and
    # how its transcripts tend to look. Written for the model, not the user.
    speech_notes: str
    # What the learner is told about transcription quality, when it is worth
    # saying. Empty when recognition is reliable enough not to need a caveat.
    accuracy_note: str = ""


HINDI = SpokenLanguage(
    code="hi",
    name="Hindi",
    native_name="हिन्दी",
    script="Devanagari",
    speech_notes=(
        "Everyday Hindi speech is full of English words (office, meeting, "
        "phone, time, problem), usually written in Devanagari. Those are "
        "already English, so they are never vocabulary worth translating. "
        "Sentences end with a verb and mark politeness through pronoun and "
        "verb endings."
    ),
)

KANNADA = SpokenLanguage(
    code="kn",
    name="Kannada",
    native_name="ಕನ್ನಡ",
    script="Kannada",
    speech_notes=(
        "Spoken Kannada differs from the literary written form, so colloquial "
        "verb endings and contractions are normal. Words carry long chains of "
        "suffixes: treat a word with its suffixes as one unit and give the "
        "English for its meaning in context, not for the bare root. English "
        "words are often mixed in."
    ),
    accuracy_note=(
        "Kannada is transcribed less accurately than Hindi, so some words may "
        "be spelled differently from how you said them."
    ),
)

TAMIL = SpokenLanguage(
    code="ta",
    name="Tamil",
    native_name="தமிழ்",
    script="Tamil",
    speech_notes=(
        "Spoken Tamil differs substantially from literary Tamil: colloquial "
        "forms, dropped endings and merged words are normal, not mistakes. "
        "Words take long chains of suffixes, so treat a word with its "
        "suffixes as one unit and give the English for its meaning in "
        "context. English words are often mixed in."
    ),
)

TELUGU = SpokenLanguage(
    code="te",
    name="Telugu",
    native_name="తెలుగు",
    script="Telugu",
    speech_notes=(
        "Spoken Telugu differs from the literary form and words carry long "
        "chains of suffixes: treat a word with its suffixes as one unit and "
        "give the English for its meaning in context. Speech recognition is "
        "weakest for Telugu, so a transcript may contain odd spellings; infer "
        "the intended word from how it would sound, but always quote exactly "
        "what is written. English words are often mixed in."
    ),
    accuracy_note=(
        "Telugu is transcribed less accurately than the other languages, so "
        "some words may be spelled differently from how you said them."
    ),
)

# Order is the order a learner sees them in.
SUPPORTED_LANGUAGES: tuple[SpokenLanguage, ...] = (HINDI, KANNADA, TAMIL, TELUGU)

_BY_CODE = {language.code: language for language in SUPPORTED_LANGUAGES}


def get_language(code: str | None) -> SpokenLanguage | None:
    """The language for a code, or None when it is not supported."""
    if not code:
        return None
    return _BY_CODE.get(code.strip().lower())
