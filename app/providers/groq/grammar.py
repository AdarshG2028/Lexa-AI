import json
import logging

from app.config import Settings
from app.core.errors import ProviderBadResponseError
from app.models import GrammarCategory, GrammarIssue, ProviderCheck, UserUtterance
from app.providers.groq.client import GroqClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an English grammar checker for a speech coaching app.

You are given numbered lines of what a learner said out loud. Find genuine
grammar mistakes and return them as JSON.

Rules:
- Only report real grammar errors. If a line is correct, say nothing about it.
- Do not report style, formality, word choice or vocabulary preferences.
- Do not report punctuation or capitalisation: this is transcribed speech, so
  punctuation comes from the transcriber and is not the speaker's mistake.
- Quote the original text exactly as given. Never rewrite it beyond the fix.
- The correction must differ from the original.
- Keep the explanation to one short sentence a learner would understand.
- confidence is 0.0 to 1.0: how sure you are this is genuinely an error.

category must be exactly one of:
tense, articles, prepositions, subject_verb_agreement, plurals, word_form,
sentence_structure, other

Respond with JSON only, in this exact shape:
{"issues": [{"line": 1, "original": "...", "corrected": "...",
             "explanation": "...", "category": "tense", "confidence": 0.9}]}

If there are no mistakes, respond with {"issues": []}."""


class GroqGrammarAnalysisProvider:
    name = "groq"

    def __init__(self, client: GroqClient, settings: Settings) -> None:
        self._client = client
        self._model = settings.groq_grammar_model or settings.groq_llm_model

    async def analyze(self, utterances: list[UserUtterance]) -> list[GrammarIssue]:
        if not utterances:
            return []

        numbered = "\n".join(
            f"{i + 1}. {u.text}" for i, u in enumerate(utterances)
        )
        response = await self._client.post(
            "/chat/completions",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": numbered},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
        )

        payload = self._parse(response)
        return self._to_issues(payload, utterances)

    def _parse(self, response) -> dict:
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderBadResponseError(
                "The grammar analysis response was missing expected fields."
            ) from exc

        try:
            payload = json.loads(content)
        except ValueError as exc:
            raise ProviderBadResponseError(
                "The grammar analysis did not return valid JSON."
            ) from exc

        if not isinstance(payload, dict) or not isinstance(
            payload.get("issues"), list
        ):
            raise ProviderBadResponseError(
                "The grammar analysis JSON did not contain an 'issues' list."
            )
        return payload

    def _to_issues(
        self, payload: dict, utterances: list[UserUtterance]
    ) -> list[GrammarIssue]:
        """Converts raw model output into validated issues.

        Anything malformed is dropped rather than failing the whole analysis:
        one bad entry should not cost the user their entire report.
        """
        issues: list[GrammarIssue] = []

        for raw in payload["issues"]:
            if not isinstance(raw, dict):
                continue

            original = str(raw.get("original", "")).strip()
            corrected = str(raw.get("corrected", "")).strip()
            explanation = str(raw.get("explanation", "")).strip()

            if not original or not corrected or original == corrected:
                continue

            issues.append(
                GrammarIssue(
                    turn_id=self._turn_for_line(raw.get("line"), utterances),
                    original=original,
                    corrected=corrected,
                    explanation=explanation or "This phrasing is not grammatical.",
                    category=_category(raw.get("category")),
                    confidence=_confidence(raw.get("confidence")),
                )
            )

        return issues

    @staticmethod
    def _turn_for_line(line, utterances: list[UserUtterance]) -> str | None:
        try:
            index = int(line) - 1
        except (TypeError, ValueError):
            return None
        return utterances[index].turn_id if 0 <= index < len(utterances) else None

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


def _category(value) -> GrammarCategory:
    try:
        return GrammarCategory(str(value).strip().lower())
    except ValueError:
        return GrammarCategory.OTHER


def _confidence(value) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 0.5
