"""The Groq vocabulary adapter.

The critical rule: counts are ours, advice is theirs. A model that miscounts
must never be able to change the numbers shown to the learner.
"""

import json

import httpx
import pytest
import respx

from app.config import Settings
from app.core.errors import ProviderBadResponseError
from app.models import UserUtterance, VocabularyIssueType, VocabularyObservation
from app.providers.groq.client import GroqClient
from app.providers.groq.vocabulary import GroqVocabularyAnalysisProvider

URL = "https://api.groq.com/openai/v1/chat/completions"

UTTERANCES = [
    UserUtterance(turn_id="t1", text="The food was very good."),
    UserUtterance(turn_id="t2", text="I will revert back to you."),
]
OBSERVATIONS = [
    VocabularyObservation(type=VocabularyIssueType.REPEATED_PHRASE,
                          text="very good", occurrences=7,
                          example="The food was very good."),
]


@pytest.fixture
def groq_settings() -> Settings:
    return Settings(vocabulary_provider="groq", groq_api_key="test-key")


@pytest.fixture
async def provider(groq_settings):
    client = GroqClient(groq_settings)
    yield GroqVocabularyAnalysisProvider(client, groq_settings)
    await client.close()


def reply(payload) -> httpx.Response:
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


@respx.mock
async def test_suggestions_are_attached_to_our_observation(provider):
    respx.post(URL).mock(return_value=reply({
        "terms": [{"text": "very good", "suggestions": ["excellent", "superb"],
                   "explanation": "Reach for something sharper."}],
        "unnatural": [],
    }))

    issues = await provider.enrich(OBSERVATIONS, UTTERANCES)

    assert len(issues) == 1
    assert issues[0].suggestions == ["excellent", "superb"]
    assert issues[0].occurrences == 7
    assert issues[0].type is VocabularyIssueType.REPEATED_PHRASE


@respx.mock
async def test_a_model_that_miscounts_cannot_change_the_number(provider):
    """This is the reason counting lives in our code."""
    respx.post(URL).mock(return_value=reply({
        "terms": [{"text": "very good", "occurrences": 2,
                   "suggestions": ["excellent"], "explanation": "x"}],
        "unnatural": [],
    }))

    issues = await provider.enrich(OBSERVATIONS, UTTERANCES)
    assert issues[0].occurrences == 7


@respx.mock
async def test_an_observation_the_model_ignored_is_still_reported(provider):
    respx.post(URL).mock(return_value=reply({"terms": [], "unnatural": []}))

    issues = await provider.enrich(OBSERVATIONS, UTTERANCES)

    assert len(issues) == 1
    assert issues[0].text == "very good"
    assert issues[0].suggestions == []
    assert issues[0].explanation


@respx.mock
async def test_an_unnatural_expression_is_added(provider):
    respx.post(URL).mock(return_value=reply({
        "terms": [],
        "unnatural": [{"text": "revert back", "suggestion": "revert",
                       "explanation": "Redundant.",
                       "example": "I will revert back to you."}],
    }))

    issues = await provider.enrich([], UTTERANCES)

    assert len(issues) == 1
    assert issues[0].type is VocabularyIssueType.UNNATURAL_EXPRESSION
    assert issues[0].suggestions == ["revert"]


@respx.mock
async def test_an_unnatural_expression_not_actually_said_is_rejected(provider):
    """Guards against the model inventing phrases the learner never used."""
    respx.post(URL).mock(return_value=reply({
        "terms": [],
        "unnatural": [{"text": "kindly do the needful", "suggestion": "please help",
                       "explanation": "x"}],
    }))

    assert await provider.enrich([], UTTERANCES) == []


@respx.mock
async def test_a_suggestion_repeating_the_original_word_is_dropped(provider):
    respx.post(URL).mock(return_value=reply({
        "terms": [{"text": "very good",
                   "suggestions": ["very good", "excellent"], "explanation": "x"}],
        "unnatural": [],
    }))

    assert (await provider.enrich(OBSERVATIONS, UTTERANCES))[0].suggestions == [
        "excellent"
    ]


@respx.mock
async def test_suggestions_are_capped(provider):
    respx.post(URL).mock(return_value=reply({
        "terms": [{"text": "very good",
                   "suggestions": [f"word{i}" for i in range(10)],
                   "explanation": "x"}],
        "unnatural": [],
    }))

    assert len((await provider.enrich(OBSERVATIONS, UTTERANCES))[0].suggestions) == 4


@respx.mock
async def test_a_no_op_unnatural_suggestion_is_dropped(provider):
    respx.post(URL).mock(return_value=reply({
        "terms": [],
        "unnatural": [{"text": "revert back", "suggestion": "revert back",
                       "explanation": "x"}],
    }))

    assert await provider.enrich([], UTTERANCES) == []


async def test_an_empty_conversation_makes_no_provider_call(provider):
    assert await provider.enrich(OBSERVATIONS, []) == []


@respx.mock
async def test_json_mode_is_requested_and_counts_are_sent(provider):
    route = respx.post(URL).mock(return_value=reply({"terms": [], "unnatural": []}))
    await provider.enrich(OBSERVATIONS, UTTERANCES)

    body = json.loads(route.calls.last.request.content)
    assert body["response_format"] == {"type": "json_object"}
    assert "very good (7 times)" in body["messages"][1]["content"]


@respx.mock
async def test_non_json_content_is_a_provider_error(provider):
    respx.post(URL).mock(return_value=reply("Sorry, I cannot."))

    with pytest.raises(ProviderBadResponseError, match="valid JSON"):
        await provider.enrich(OBSERVATIONS, UTTERANCES)


@respx.mock
async def test_malformed_entries_are_skipped_not_fatal(provider):
    respx.post(URL).mock(return_value=reply({
        "terms": ["not an object", {"no_text": True}],
        "unnatural": ["also wrong"],
    }))

    issues = await provider.enrich(OBSERVATIONS, UTTERANCES)
    assert len(issues) == 1
    assert issues[0].occurrences == 7


@respx.mock
async def test_the_prompt_excludes_grammar_from_vocabulary(provider):
    """Grammar is reported by its own endpoint; showing it twice in a unified
    report would be noise."""
    route = respx.post(URL).mock(return_value=reply({"terms": [], "unnatural": []}))
    await provider.enrich(OBSERVATIONS, UTTERANCES)

    system = json.loads(route.calls.last.request.content)["messages"][0]["content"]
    assert "subject-verb agreement" in system.lower()
    assert "analysed separately" in system.lower()
