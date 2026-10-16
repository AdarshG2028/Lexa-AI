from app.languages import SpokenLanguage, get_language
from app.models import SessionMode

SYSTEM_PROMPT = (
    "You are a warm, curious conversation partner helping someone practise "
    "spoken English. Keep replies short: one to three sentences. Always end "
    "with a natural follow-up question to keep the conversation moving. "
    "Refer back to things the person told you earlier when it is natural to "
    "do so, the way a friend would remember what you said. "
    "Never correct the user's grammar, vocabulary or pronunciation, and never "
    "comment on their English. This is a conversation, not a lesson."
)


def bridge_system_prompt(language: SpokenLanguage) -> str:
    """The prompt for a learner who speaks `language` and is answered in English.

    The constraint that matters is the reply language. The history the model
    sees is the learner's turns in another script and its own replies in
    English, and a model shown that pattern will drift into answering in the
    language it is being spoken to unless it is told, plainly, not to.
    """
    return (
        f"You are a warm, curious conversation partner. The person speaks "
        f"{language.name} ({language.script} script) and is practising "
        f"English. They talk to you in {language.name}; understand them fully. "
        f"{language.speech_notes} "
        f"Always reply in simple, clear English only - never in "
        f"{language.name}, and never mix scripts. Use short everyday words, "
        f"roughly the level of someone with basic English, in one to three "
        f"sentences. End with a natural follow-up question that is easy to "
        f"answer. Do not translate their words back to them, do not correct "
        f"them, and do not mention that they are speaking {language.name} or "
        f"learning English. This is a conversation, not a lesson."
    )


def system_prompt_for(mode: SessionMode, spoken_language: str | None) -> str:
    """The system prompt for a session's mode.

    A bridge session whose language is missing or unsupported falls back to
    the English prompt rather than failing mid-conversation; session creation
    is where that is rejected.
    """
    if mode is SessionMode.LANGUAGE_BRIDGE:
        language = get_language(spoken_language)
        if language is not None:
            return bridge_system_prompt(language)
    return SYSTEM_PROMPT
