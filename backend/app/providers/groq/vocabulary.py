import json
import logging

from app.config import Settings
from app.core.errors import ProviderBadResponseError
from app.models import (
    ProviderCheck,
    UserUtterance,
    VocabularyIssue,
    VocabularyIssueType,
    VocabularyObservation,
)
from app.providers.groq.client import GroqClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You help a learner of English improve their word choice.

You are given: (1) words and phrases they leaned on, already counted, and
(2) the sentences they actually said.

Do two things.

For each counted term, suggest 3-4 stronger or more precise alternatives that
would fit how they used it. Alternatives must be natural in spoken English,
not obscure or literary. Write one short sentence of advice.

Separately, list any expressions that are grammatically possible but sound
unnatural to a native speaker: redundant pairs like "revert back", wrong
prepositions like "discuss about", or phrasing carried over from another
language.

Grammar is analysed separately and reported to the learner already. Never
include verb tense, subject-verb agreement, duplicated subjects, articles,
plurals or word order. If correcting it would be a grammar fix rather than a
word-choice fix, leave it out.

Never change the counts you are given. Never invent a term that was not in
the list or the sentences.

Respond with JSON only:
{"terms": [{"text": "very good", "suggestions": ["excellent", "impressive"],
            "explanation": "..."}],
 "unnatural": [{"text": "revert back", "suggestion": "revert",
                "explanation": "...", "example": "the sentence they said"}]}

Use empty lists where you have nothing to add."""


class GroqVocabularyAnalysisProvider:
    name = "groq"

    def __init__(self, client: GroqClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.groq_vocabulary_model or settings.groq_llm_model

    async def enrich(
        self,
        observations: list[VocabularyObservation],
        utterances: list[UserUtterance],
    ) -> list[VocabularyIssue]:
        if not utterances:
            return []

        counted = "\n".join(
            f"- {o.text} ({o.occurrences} times)" for o in observations
        ) or "- (none)"
        spoken = "\n".join(u.text for u in utterances)

        response = await self._client.post(
            "/chat/completions",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"COUNTED TERMS:\n{counted}\n\nWHAT THEY SAID:\n{spoken}",
                    },
                ],
                "temperature": 0.4,
                "response_format": {"type": "json_object"},
            },
        )

        payload = self._parse(response)
        return self._merge(payload, observations, utterances)

    def _parse(self, response) -> dict:
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderBadResponseError(
                "The vocabulary response was missing expected fields."
            ) from exc

        try:
            payload = json.loads(content)
        except ValueError as exc:
            raise ProviderBadResponseError(
                "The vocabulary analysis did not return valid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise ProviderBadResponseError(
                "The vocabulary analysis JSON was not an object."
            )
        return payload

    def _merge(
        self,
        payload: dict,
        observations: list[VocabularyObservation],
        utterances: list[UserUtterance],
    ) -> list[VocabularyIssue]:
        """Attaches model advice to measured observations.

        Counts come from our own arithmetic and are never taken from the
        model, which is free to miscount. An observation the model ignored is
        still reported, just without alternatives.
        """
        advice = {}
        for raw in _as_list(payload.get("terms")):
            if isinstance(raw, dict) and raw.get("text"):
                advice[str(raw["text"]).strip().lower()] = raw

        issues: list[VocabularyIssue] = []
        for observation in observations:
            raw = advice.get(observation.text.lower(), {})
            issues.append(
                VocabularyIssue(
                    type=observation.type,
                    text=observation.text,
                    occurrences=observation.occurrences,
                    example=observation.example,
                    suggestions=_clean_suggestions(
                        raw.get("suggestions"), observation.text
                    ),
                    explanation=str(raw.get("explanation", "")).strip()
                    or f"You used '{observation.text}' {observation.occurrences} times.",
                )
            )

        spoken = "\n".join(u.text for u in utterances).lower()
        for raw in _as_list(payload.get("unnatural")):
            if not isinstance(raw, dict):
                continue
            text = str(raw.get("text", "")).strip()
            suggestion = str(raw.get("suggestion", "")).strip()
            if not text or not suggestion or text.lower() == suggestion.lower():
                continue
            if text.lower() not in spoken:
                continue

            issues.append(
                VocabularyIssue(
                    type=VocabularyIssueType.UNNATURAL_EXPRESSION,
                    text=text,
                    occurrences=spoken.count(text.lower()) or 1,
                    example=str(raw.get("example", "")).strip()
                    or _example_for(text, utterances),
                    suggestions=[suggestion],
                    explanation=str(raw.get("explanation", "")).strip()
                    or "This phrasing sounds unnatural to a native speaker.",
                    confidence=0.8,
                )
            )

        return issues

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


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _clean_suggestions(value, term: str) -> list[str]:
    """Keeps up to four usable alternatives, dropping anything that repeats
    the word it is meant to replace."""
    out: list[str] = []
    for item in _as_list(value):
        text = str(item).strip()
        if text and text.lower() != term.lower() and text not in out:
            out.append(text)
    return out[:4]


def _example_for(text: str, utterances: list[UserUtterance]) -> str:
    for utterance in utterances:
        if text.lower() in utterance.text.lower():
            return utterance.text
    return utterances[0].text if utterances else ""
