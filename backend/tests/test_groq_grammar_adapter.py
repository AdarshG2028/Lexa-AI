"""The Groq grammar adapter, against a mocked transport.

LLM output is untrusted input: it can be malformed, invent no-op corrections,
or use categories that do not exist. None of that should break an analysis.
"""

import json

import httpx
import pytest
import respx

from app.config import Settings
from app.core.errors import ProviderBadResponseError
from app.models import GrammarCategory, UserUtterance
from app.providers.groq.client import GroqClient
from app.providers.groq.grammar import GroqGrammarAnalysisProvider

URL = "https://api.groq.com/openai/v1/chat/completions"


@pytest.fixture
def groq_settings() -> Settings:
    return Settings(grammar_provider="groq", groq_api_key="test-key")


@pytest.fixture
async def provider(groq_settings):
    client = GroqClient(groq_settings)
    yield GroqGrammarAnalysisProvider(client, groq_settings)
    await client.close()


def reply(payload) -> httpx.Response:
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return httpx.Response(
        200, json={"choices": [{"message": {"content": content}}]}
    )


UTTERANCES = [
    UserUtterance(turn_id="turn-a", text="I go to college yesterday."),
    UserUtterance(turn_id="turn-b", text="He go to school."),
]


@respx.mock
async def test_issues_are_mapped_with_their_turn(provider):
    respx.post(URL).mock(return_value=reply({"issues": [
        {"line": 2, "original": "He go to school.",
         "corrected": "He goes to school.",
         "explanation": "Singular subject.", "category": "subject_verb_agreement",
         "confidence": 0.95},
    ]}))

    issues = await provider.analyze(UTTERANCES)

    assert len(issues) == 1
    assert issues[0].turn_id == "turn-b"
    assert issues[0].category is GrammarCategory.SUBJECT_VERB_AGREEMENT
    assert issues[0].confidence == 0.95


@respx.mock
async def test_no_mistakes_returns_an_empty_list(provider):
    respx.post(URL).mock(return_value=reply({"issues": []}))

    assert await provider.analyze(UTTERANCES) == []


async def test_an_empty_conversation_makes_no_provider_call(provider):
    """respx would raise on an unexpected request, so this asserts no call."""
    assert await provider.analyze([]) == []


@respx.mock
async def test_json_mode_is_requested(provider):
    route = respx.post(URL).mock(return_value=reply({"issues": []}))
    await provider.analyze(UTTERANCES)

    body = json.loads(route.calls.last.request.content)
    assert body["response_format"] == {"type": "json_object"}
    assert "1. I go to college yesterday." in body["messages"][1]["content"]


@respx.mock
async def test_a_no_op_correction_is_discarded(provider):
    respx.post(URL).mock(return_value=reply({"issues": [
        {"line": 1, "original": "same", "corrected": "same",
         "explanation": "", "category": "tense", "confidence": 0.9},
    ]}))

    assert await provider.analyze(UTTERANCES) == []


@respx.mock
async def test_an_unknown_category_falls_back_to_other(provider):
    respx.post(URL).mock(return_value=reply({"issues": [
        {"line": 1, "original": "a", "corrected": "b", "explanation": "x",
         "category": "invented_category", "confidence": 0.9},
    ]}))

    issues = await provider.analyze(UTTERANCES)
    assert issues[0].category is GrammarCategory.OTHER


@respx.mock
async def test_a_nonsense_confidence_falls_back_to_a_default(provider):
    respx.post(URL).mock(return_value=reply({"issues": [
        {"line": 1, "original": "a", "corrected": "b", "explanation": "x",
         "category": "tense", "confidence": "very sure"},
    ]}))

    issues = await provider.analyze(UTTERANCES)
    assert issues[0].confidence == 0.5


@respx.mock
async def test_an_out_of_range_confidence_is_clamped(provider):
    respx.post(URL).mock(return_value=reply({"issues": [
        {"line": 1, "original": "a", "corrected": "b", "explanation": "x",
         "category": "tense", "confidence": 7},
    ]}))

    issues = await provider.analyze(UTTERANCES)
    assert issues[0].confidence == 1.0


@respx.mock
async def test_a_line_number_out_of_range_leaves_the_turn_unset(provider):
    respx.post(URL).mock(return_value=reply({"issues": [
        {"line": 99, "original": "a", "corrected": "b", "explanation": "x",
         "category": "tense", "confidence": 0.9},
    ]}))

    assert (await provider.analyze(UTTERANCES))[0].turn_id is None


@respx.mock
async def test_one_malformed_entry_does_not_lose_the_others(provider):
    """A single bad row should not cost the user their whole report."""
    respx.post(URL).mock(return_value=reply({"issues": [
        "not an object",
        {"original": "", "corrected": "b", "explanation": "x"},
        {"line": 1, "original": "a", "corrected": "b", "explanation": "good",
         "category": "tense", "confidence": 0.9},
    ]}))

    issues = await provider.analyze(UTTERANCES)
    assert len(issues) == 1
    assert issues[0].explanation == "good"


@respx.mock
async def test_a_missing_explanation_gets_a_sensible_default(provider):
    respx.post(URL).mock(return_value=reply({"issues": [
        {"line": 1, "original": "a", "corrected": "b", "category": "tense",
         "confidence": 0.9},
    ]}))

    assert (await provider.analyze(UTTERANCES))[0].explanation


@respx.mock
async def test_non_json_content_is_a_provider_error(provider):
    respx.post(URL).mock(return_value=reply("I'm afraid I can't do that."))

    with pytest.raises(ProviderBadResponseError, match="valid JSON"):
        await provider.analyze(UTTERANCES)


@respx.mock
async def test_json_without_an_issues_list_is_a_provider_error(provider):
    respx.post(URL).mock(return_value=reply({"result": "fine"}))

    with pytest.raises(ProviderBadResponseError, match="issues"):
        await provider.analyze(UTTERANCES)


@respx.mock
async def test_a_malformed_completion_is_a_provider_error(provider):
    respx.post(URL).mock(return_value=httpx.Response(200, json={"nope": True}))

    with pytest.raises(ProviderBadResponseError):
        await provider.analyze(UTTERANCES)
