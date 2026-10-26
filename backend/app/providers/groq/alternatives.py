import json
import logging

from app.config import Settings
from app.core.errors import ProviderBadResponseError
from app.languages import SpokenLanguage
from app.models import (
    AlternativeKind,
    EnglishAlternative,
    ProviderCheck,
    UserUtterance,
)
from app.providers.groq.client import GroqClient

logger = logging.getLogger(__name__)

# "Popular" is stated as a concrete test: a word an everyday speaker reaches
# for, not a rare or formal one. The old wording asked for "harder" words,
# which is what produced English-to-English synonym upgrades.
SYSTEM_PROMPT = """You help someone who speaks {name} learn the English for \
words and phrases they actually used.

They spoke {name} ({script} script) in a conversation. You are given their \
sentences exactly as speech recognition wrote them.

{speech_notes}

Pick the words and expressions they said that are worth knowing the English \
for, and give the English.

INCLUDE
- Common words: everyday {name} words a learner is likely to reach for and may \
not know in English - the kind of word that appears in ordinary conversation \
about work, money, time, plans, feelings and daily life.
- Phrases: multi-word expressions, idioms and fixed expressions, especially \
where the natural English is not a word-for-word translation.

LEAVE OUT
- Anything written in Latin letters. Every "original" must be {script} script \
only - never English letters, and never a span that mixes the two scripts.
- English words written in {script}. Everyday speech is full of them and the \
learner already knows them. {loanword_note}
- Names of people and places, numbers, and greetings.
- Anything the learner already said in English.

RULES
- "original" is copied exactly as written in their sentence, in {script} \
script, with any suffixes. Never rewrite, correct or transliterate it, even if \
it looks misspelled.
- "original" is the SHORTEST span that carries the expression: one word, or a \
phrase of two to five words. Never a whole sentence or clause. If a sentence \
contains one useful word, give that word alone, not the sentence around it.
- "english" is the natural, reusable English for that span, in Latin script \
only: a word ("work", "need", "hurry") or a chunk a learner could drop into \
other sentences ("take care of", "as soon as possible"). Do not give a full \
sentence and do not add a subject such as I or we. Never answer with a fancier \
synonym of an English word: the left side must be {name}, the right side English.
- "example" is one short, simple English sentence that uses "english", written \
in the first person (I / we) so it reads as the learner saying it.
- The sentences come from speech recognition and may be misspelled. If a word \
looks misspelled, work out the word they most likely said from the sentence \
around it. If you cannot tell what was meant, leave it out: a wrong English \
word is worse than a missing one.
- Prefer fewer, better items: at most 12, most useful first, no duplicates.
- If nothing qualifies, return an empty list.

Respond with JSON only:
{{"items": [{{"original": "...", "english": "...", "example": "..."}}]}}"""


class GroqEnglishAlternativesProvider:
    name = "groq"

    def __init__(self, client: GroqClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.groq_alternatives_model or settings.groq_llm_model

    async def suggest(
        self, language: SpokenLanguage, utterances: list[UserUtterance]
    ) -> list[EnglishAlternative]:
        if not utterances:
            return []

        spoken = "\n".join(f"- {u.text}" for u in utterances)
        response = await self._client.post(
            "/chat/completions",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": _prompt_for(language)},
                    {"role": "user", "content": f"THEIR SENTENCES:\n{spoken}"},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
        )
        return _to_alternatives(_parse(response))

    async def check(self) -> ProviderCheck:
        listed = await self._client.list_model_ids()
        found = self._model in listed
        return ProviderCheck(
            provider=self.name,
            model=self._model,
            model_listed=found,
            note=None if found else (
                "This model ID was not in the provider's model list. It may "
                "have been retired or may not be enabled for this API key."
            ),
        )


def _prompt_for(language: SpokenLanguage) -> str:
    return SYSTEM_PROMPT.format(
        name=language.name,
        script=language.script,
        speech_notes=language.speech_notes,
        loanword_note=_loanword_note(language),
    )


def _loanword_note(language: SpokenLanguage) -> str:
    """A few concrete loanwords, so the exclusion is not left to guesswork.

    Only languages whose list is populated get examples; the rule above still
    applies to the others.
    """
    if not language.loanwords:
        return ""
    examples = sorted(language.loanwords)[:10]
    return f"Examples in {language.script} script: {', '.join(examples)}."


def _parse(response) -> dict:
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProviderBadResponseError(
            "The alternatives response was missing expected fields."
        ) from exc

    try:
        payload = json.loads(content)
    except (ValueError, TypeError) as exc:
        raise ProviderBadResponseError(
            "The alternatives analysis did not return valid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise ProviderBadResponseError(
            "The alternatives analysis JSON was not an object."
        )
    return payload


def _to_alternatives(payload: dict) -> list[EnglishAlternative]:
    """Reads the model's items, skipping any that are unusable.

    Only structure is checked here. Whether an item is genuinely something
    the learner said is the service's job, since that check has to hold for
    every provider, not just this one.
    """
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return []

    items: list[EnglishAlternative] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        original = str(raw.get("original", "")).strip()
        english = str(raw.get("english", "")).strip()
        if not original or not english:
            continue
        items.append(
            EnglishAlternative(
                original=original,
                english=english,
                # Replaced by the service from the matched text; a single
                # word and a phrase are told apart by counting, not asking.
                kind=AlternativeKind.PHRASE if " " in original else AlternativeKind.WORD,
                example=str(raw.get("example", "")).strip(),
            )
        )
    return items
