"""The language bridge: a learner speaks their own language, is answered in
English, and is shown English alternatives for what they said.

It is a separate feature from English coaching and these tests are as much
about the boundary as the behaviour: the English analyses must refuse a
bridge conversation, the bridge analysis must refuse an English one, and an
ordinary session must be exactly what it was before this existed.
"""

import asyncio

import httpx
import pytest
import respx

from app.analysis.alternatives import MAX_ITEMS, clean
from app.analysis.alternatives_repository import (
    InMemoryEnglishAlternativesRepository,
    SqlEnglishAlternativesRepository,
)
from app.api.deps import get_registry
from app.config import Settings
from app.conversation.prompts import SYSTEM_PROMPT, system_prompt_for
from app.core.ratelimit import classify
from app.db.engine import create_engine, create_session_factory, create_tables
from app.languages import SUPPORTED_LANGUAGES, get_language
from app.models import (
    AlternativeKind,
    ChatReply,
    EnglishAlternative,
    EnglishAlternativesAnalysis,
    ProviderCheck,
    Session,
    SessionMode,
    UserUtterance,
)
from app.providers.groq.alternatives import GroqEnglishAlternativesProvider
from app.providers.groq.client import GroqClient
from app.providers.groq.stt import GroqSpeechToTextProvider
from app.providers.mock.stt import MOCK_TRANSCRIPT, MOCK_TRANSCRIPTS
from app.providers.registry import ProviderRegistry
from app.sessions.sql import SqlSessionRepository
from tests.conftest import make_wav

BASE_URL = "https://api.groq.com/openai/v1"
HINDI = get_language("hi")


async def start_bridge(client, language: str = "hi") -> str:
    response = await client.post(
        "/api/v1/sessions",
        json={"mode": "language_bridge", "spoken_language": language},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def speak(client, session_id: str) -> dict:
    response = await client.post(
        f"/api/v1/sessions/{session_id}/turns",
        files={"file": ("speech.wav", make_wav(1.5), "audio/wav")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def alt(original: str, english: str, example: str = "") -> EnglishAlternative:
    return EnglishAlternative(
        original=original, english=english, kind=AlternativeKind.PHRASE, example=example
    )


def said(*texts: str) -> list[UserUtterance]:
    return [UserUtterance(turn_id=f"t{i}", text=text) for i, text in enumerate(texts)]


# --- the languages --------------------------------------------------------


def test_the_four_languages_are_supported_in_the_order_a_learner_sees_them():
    assert [language.code for language in SUPPORTED_LANGUAGES] == ["hi", "kn", "ta", "te"]


def test_each_language_has_its_own_script_and_notes():
    scripts = {language.script for language in SUPPORTED_LANGUAGES}
    notes = {language.speech_notes for language in SUPPORTED_LANGUAGES}

    assert len(scripts) == 4
    assert len(notes) == 4


def test_a_language_code_is_matched_loosely_and_unknown_codes_are_none():
    assert get_language(" HI ").code == "hi"
    assert get_language("fr") is None
    assert get_language("") is None
    assert get_language(None) is None


# --- starting a session ---------------------------------------------------


async def test_a_session_with_no_mode_is_an_ordinary_english_session(client):
    body = (await client.post("/api/v1/sessions")).json()

    assert body["mode"] == "english_coach"
    assert body["spoken_language"] is None


async def test_a_bridge_session_records_its_language(client):
    body = (
        await client.post(
            "/api/v1/sessions",
            json={"mode": "language_bridge", "spoken_language": "ta"},
        )
    ).json()

    assert body["mode"] == "language_bridge"
    assert body["spoken_language"] == "ta"


async def test_a_bridge_session_needs_a_language(client):
    response = await client.post("/api/v1/sessions", json={"mode": "language_bridge"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_LANGUAGE"


async def test_an_unsupported_language_is_refused_and_the_options_are_listed(client):
    response = await client.post(
        "/api/v1/sessions",
        json={"mode": "language_bridge", "spoken_language": "fr"},
    )

    error = response.json()["error"]
    assert response.status_code == 400
    assert error["code"] == "UNSUPPORTED_LANGUAGE"
    assert error["details"]["supported"] == ["hi", "kn", "ta", "te"]


async def test_a_language_on_an_english_session_is_dropped(client):
    body = (
        await client.post(
            "/api/v1/sessions",
            json={"mode": "english_coach", "spoken_language": "hi"},
        )
    ).json()

    assert body["mode"] == "english_coach"
    assert body["spoken_language"] is None


# --- the conversation -----------------------------------------------------


async def test_a_bridge_turn_is_transcribed_in_the_chosen_language(client):
    session_id = await start_bridge(client, "kn")

    turn = await speak(client, session_id)

    assert turn["transcript"] == MOCK_TRANSCRIPTS["kn"]


async def test_an_english_turn_is_unaffected_by_the_bridge_feature(client, session_id):
    turn = await speak(client, session_id)

    assert turn["transcript"] == MOCK_TRANSCRIPT


def test_the_bridge_prompt_names_the_language_and_demands_english_replies():
    prompt = system_prompt_for(SessionMode.LANGUAGE_BRIDGE, "hi")

    assert "Hindi" in prompt
    assert "Devanagari" in prompt
    assert "reply in simple, clear English only" in prompt
    assert prompt != SYSTEM_PROMPT


def test_every_language_gets_a_different_prompt():
    prompts = {
        system_prompt_for(SessionMode.LANGUAGE_BRIDGE, language.code)
        for language in SUPPORTED_LANGUAGES
    }

    assert len(prompts) == 4


def test_english_sessions_keep_the_original_prompt_exactly():
    assert system_prompt_for(SessionMode.ENGLISH_COACH, None) == SYSTEM_PROMPT
    assert system_prompt_for(SessionMode.ENGLISH_COACH, "hi") == SYSTEM_PROMPT


def test_a_bridge_session_with_no_usable_language_falls_back_not_fails():
    assert system_prompt_for(SessionMode.LANGUAGE_BRIDGE, None) == SYSTEM_PROMPT
    assert system_prompt_for(SessionMode.LANGUAGE_BRIDGE, "xx") == SYSTEM_PROMPT


async def test_the_model_is_shown_the_bridge_prompt_in_a_bridge_session(
    app, client, settings
):
    """The learner's turns are in another script and the model's own replies
    are English; unless it is told, it drifts into answering in the language
    it is spoken to. That instruction has to actually reach the model."""

    class RecordingLLM:
        name = "recording"

        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def reply(self, messages):
            self.prompts.append(messages[0].content)
            return ChatReply(text="Sounds good. What will you do next?", model="rec")

        async def check(self):
            return ProviderCheck(provider=self.name)

    recorder = RecordingLLM()

    class Registry(ProviderRegistry):
        def llm(self):
            return recorder

    app.dependency_overrides[get_registry] = lambda: Registry(settings)

    await speak(client, await start_bridge(client, "te"))
    english = (await client.post("/api/v1/sessions")).json()["id"]
    await speak(client, english)

    assert "Telugu" in recorder.prompts[0]
    assert recorder.prompts[1] == SYSTEM_PROMPT


# --- keeping the two features apart ---------------------------------------


@pytest.mark.parametrize(
    "kind", ["grammar", "vocabulary", "fluency", "pronunciation"]
)
async def test_the_english_analyses_refuse_a_bridge_conversation(client, kind):
    session_id = await start_bridge(client)
    await speak(client, session_id)

    response = await client.post(f"/api/v1/sessions/{session_id}/analysis/{kind}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ANALYSIS_NOT_APPLICABLE"


async def test_nothing_is_stored_when_an_english_analysis_is_refused(client):
    session_id = await start_bridge(client)
    await speak(client, session_id)
    await client.post(f"/api/v1/sessions/{session_id}/analysis/grammar")

    stored = await client.get(f"/api/v1/sessions/{session_id}/analysis/grammar")

    assert stored.status_code == 404


async def test_the_english_analyses_still_run_on_an_english_conversation(
    client, session_id
):
    await speak(client, session_id)

    response = await client.post(f"/api/v1/sessions/{session_id}/analysis/grammar")

    assert response.status_code == 200


async def test_alternatives_refuse_an_english_conversation(client, session_id):
    await speak(client, session_id)

    response = await client.post(
        f"/api/v1/sessions/{session_id}/analysis/english-alternatives"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ANALYSIS_NOT_APPLICABLE"


# --- the report -----------------------------------------------------------


async def test_alternatives_are_not_found_until_they_have_been_run(client):
    session_id = await start_bridge(client)

    response = await client.get(
        f"/api/v1/sessions/{session_id}/analysis/english-alternatives"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"


@pytest.mark.parametrize("code", ["hi", "kn", "ta", "te"])
async def test_a_conversation_in_each_language_yields_alternatives(client, code):
    session_id = await start_bridge(client, code)
    turn = await speak(client, session_id)

    response = await client.post(
        f"/api/v1/sessions/{session_id}/analysis/english-alternatives"
    )

    body = response.json()
    assert response.status_code == 200
    assert body["spoken_language"] == code
    assert body["item_count"] >= 1
    for item in body["items"]:
        # Every item is something the learner genuinely said, and says which turn.
        assert item["original"] in turn["transcript"]
        assert item["turn_id"] == turn["turn_id"]
        assert item["english"].isascii()


async def test_the_stored_report_matches_the_one_that_was_run(client):
    session_id = await start_bridge(client)
    await speak(client, session_id)
    url = f"/api/v1/sessions/{session_id}/analysis/english-alternatives"

    created = (await client.post(url)).json()
    fetched = (await client.get(url)).json()

    assert fetched["items"] == created["items"]
    assert fetched["created_at"] == created["created_at"]


async def test_a_conversation_with_nothing_said_says_so_rather_than_inventing(client):
    session_id = await start_bridge(client)

    body = (
        await client.post(f"/api/v1/sessions/{session_id}/analysis/english-alternatives")
    ).json()

    assert body["items"] == []
    assert body["turns_analyzed"] == 0
    assert "no spoken turns" in body["note"]


async def test_the_accuracy_caveat_is_shown_for_languages_that_need_one(client):
    session_id = await start_bridge(client, "te")
    await speak(client, session_id)

    body = (
        await client.post(f"/api/v1/sessions/{session_id}/analysis/english-alternatives")
    ).json()

    assert "less accurately" in body["note"]


def test_the_alternatives_endpoint_counts_against_the_analysis_limit():
    assert (
        classify("POST", "/api/v1/sessions/abc/analysis/english-alternatives")
        == "analysis"
    )


# --- what is allowed to be reported ---------------------------------------


def test_an_item_that_was_never_said_is_dropped():
    items = clean(
        [alt("पूरी तरह से बनावटी वाक्य", "a made up sentence")],
        said("मुझे थोड़ा सा समय चाहिए"),
    )

    assert items == []


def test_a_kept_item_shows_the_words_as_transcribed_not_as_the_model_wrote_them():
    """Transcripts of the Dravidian languages carry spelling noise, and the
    model tidies it. The learner should see what was actually heard."""
    items = clean(
        [alt("ಮಾರುಕಟ್ಟೆಗೆ ಹೋಗಿದ್ದೆ", "went to the market")],
        said("ನಾನು ಇಂದು ಮಾರುಕಟ್ಟಿಗೆ ಹೋಗಿದ್ದೆ ಮತ್ತು"),
    )

    assert [item.original for item in items] == ["ಮಾರುಕಟ್ಟಿಗೆ ಹೋಗಿದ್ದೆ"]


def test_punctuation_in_the_transcript_does_not_defeat_matching():
    items = clean(
        [alt("थोड़ा सा समय", "a little time")],
        said("मुझे, थोड़ा सा समय। चाहिए"),
    )

    assert [item.original for item in items] == ["थोड़ा सा समय"]


def test_english_that_is_still_in_the_learners_script_is_dropped():
    items = clean(
        [alt("थोड़ा सा समय", "थोड़ा समय")], said("मुझे थोड़ा सा समय चाहिए")
    )

    assert items == []


def test_a_word_that_is_already_english_is_not_reported():
    items = clean([alt("office", "office")], said("मैं office जा रहा हूँ"))

    assert items == []


def test_the_same_phrase_is_reported_once():
    items = clean(
        [alt("थोड़ा सा समय", "a little time"), alt("थोड़ा सा समय", "some time")],
        said("मुझे थोड़ा सा समय चाहिए"),
    )

    assert len(items) == 1
    assert items[0].english == "a little time"


def test_the_report_is_capped():
    words = [f"शब्द{i}" for i in range(30)]
    items = clean(
        [alt(word, f"word number {i}") for i, word in enumerate(words)],
        said(" ".join(words)),
    )

    assert len(items) == MAX_ITEMS


def test_one_word_is_a_word_and_several_are_a_phrase():
    items = clean(
        [alt("जिम्मेदारी", "responsibility"), alt("थोड़ा सा समय", "a little time")],
        said("मुझे जिम्मेदारी और थोड़ा सा समय चाहिए"),
    )

    kinds = {item.original: item.kind for item in items}
    assert kinds["जिम्मेदारी"] is AlternativeKind.WORD
    assert kinds["थोड़ा सा समय"] is AlternativeKind.PHRASE


def test_an_item_is_attributed_to_the_turn_it_came_from():
    items = clean(
        [alt("दूसरा वाक्यांश", "second phrase")],
        said("पहली बात यहाँ है", "यह दूसरा वाक्यांश है"),
    )

    assert items[0].turn_id == "t1"


# --- storage --------------------------------------------------------------


def make_analysis(session_id: str, *items: EnglishAlternative) -> EnglishAlternativesAnalysis:
    return EnglishAlternativesAnalysis(
        session_id=session_id,
        spoken_language="hi",
        provider="mock",
        turns_analyzed=1,
        items=list(items),
    )


@pytest.fixture
async def sql_repository(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await create_tables(engine)
    factory = create_session_factory(engine)
    # The report belongs to a session row, so one has to exist.
    sessions = SqlSessionRepository(factory)
    await sessions.create(Session(id="s1", mode=SessionMode.LANGUAGE_BRIDGE, spoken_language="hi"))
    await sessions.create(Session(id="s2", mode=SessionMode.LANGUAGE_BRIDGE, spoken_language="hi"))
    yield SqlEnglishAlternativesRepository(factory)
    await engine.dispose()


@pytest.fixture(params=["memory", "database"])
async def repository(request, sql_repository):
    if request.param == "memory":
        return InMemoryEnglishAlternativesRepository()
    return sql_repository


async def test_a_saved_report_reads_back_intact(repository):
    saved = make_analysis("s1", alt("थोड़ा सा समय", "a little time", "I need a little time."))
    await repository.save(saved)

    loaded = await repository.get("s1")

    assert loaded is not None
    assert [(i.original, i.english, i.example) for i in loaded.items] == [
        ("थोड़ा सा समय", "a little time", "I need a little time.")
    ]
    assert loaded.spoken_language == "hi"


async def test_a_report_that_was_never_saved_is_none(repository):
    assert await repository.get("s2") is None


async def test_running_it_again_replaces_the_report(repository):
    await repository.save(make_analysis("s1", alt("पहला", "first")))
    await repository.save(make_analysis("s1", alt("दूसरा", "second")))

    loaded = await repository.get("s1")

    assert [i.english for i in loaded.items] == ["second"]


async def test_item_order_is_preserved(repository):
    await repository.save(
        make_analysis("s1", alt("क", "a"), alt("ख", "b"), alt("ग", "c"))
    )

    loaded = await repository.get("s1")

    assert [i.english for i in loaded.items] == ["a", "b", "c"]


async def test_concurrent_first_saves_both_succeed(sql_repository):
    """The race that produced "the analysis could not be saved" for the English
    analyses: two writers, no row yet, one unique constraint."""
    await asyncio.gather(
        sql_repository.save(make_analysis("s1", alt("क", "a"))),
        sql_repository.save(make_analysis("s1", alt("ख", "b"))),
        sql_repository.save(make_analysis("s1", alt("ग", "c"))),
    )

    assert await sql_repository.get("s1") is not None


async def test_a_sessions_mode_and_language_survive_the_database(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'modes.db'}")
    await create_tables(engine)
    repository = SqlSessionRepository(create_session_factory(engine))

    await repository.create(
        Session(id="b", mode=SessionMode.LANGUAGE_BRIDGE, spoken_language="kn")
    )
    await repository.create(Session(id="e"))
    bridge, english = await repository.get("b"), await repository.get("e")
    await engine.dispose()

    assert (bridge.mode, bridge.spoken_language) == (SessionMode.LANGUAGE_BRIDGE, "kn")
    assert (english.mode, english.spoken_language) == (SessionMode.ENGLISH_COACH, None)


async def test_a_session_stored_before_modes_existed_reads_as_english(tmp_path):
    from sqlalchemy import text

    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'legacy.db'}")
    await create_tables(engine)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO sessions (id, status, started_at, last_activity_at) "
                "VALUES ('old', 'active', '2026-01-01 00:00:00', '2026-01-01 00:00:00')"
            )
        )
    repository = SqlSessionRepository(create_session_factory(engine))

    loaded = await repository.get("old")
    await engine.dispose()

    assert loaded.mode is SessionMode.ENGLISH_COACH
    assert loaded.spoken_language is None


# --- the Groq adapters ----------------------------------------------------


@pytest.fixture
def groq_settings() -> Settings:
    return Settings(
        stt_provider="groq",
        llm_provider="groq",
        alternatives_provider="groq",
        groq_api_key="test-key",
        groq_base_url=BASE_URL,
    )


@pytest.fixture
async def groq_client(groq_settings):
    c = GroqClient(groq_settings)
    yield c
    await c.close()


def completion(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


@respx.mock
async def test_the_adapter_reads_items_from_the_models_json(groq_client, groq_settings):
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=completion(
            '{"items": [{"original": "थोड़ा सा समय", "english": "a little time",'
            ' "example": "I need a little time."}]}'
        )
    )
    provider = GroqEnglishAlternativesProvider(groq_client, groq_settings)

    items = await provider.suggest(HINDI, said("मुझे थोड़ा सा समय चाहिए"))

    assert [(i.original, i.english) for i in items] == [
        ("थोड़ा सा समय", "a little time")
    ]


@respx.mock
async def test_the_prompt_is_specific_to_the_language_and_asks_for_json(
    groq_client, groq_settings
):
    import json

    route = respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=completion('{"items": []}')
    )
    provider = GroqEnglishAlternativesProvider(groq_client, groq_settings)

    await provider.suggest(get_language("kn"), said("ನನಗೆ ಸ್ವಲ್ಪ ಸಮಯ ಬೇಕು"))

    sent = json.loads(route.calls.last.request.content)
    system = sent["messages"][0]["content"]
    assert "Kannada" in system
    assert "Spoken Kannada differs" in system
    assert sent["response_format"] == {"type": "json_object"}
    assert "ನನಗೆ ಸ್ವಲ್ಪ ಸಮಯ ಬೇಕು" in sent["messages"][1]["content"]


@respx.mock
async def test_a_reply_that_is_not_json_is_a_provider_error(groq_client, groq_settings):
    from app.core.errors import ProviderBadResponseError

    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=completion("Here are some words you could learn!")
    )
    provider = GroqEnglishAlternativesProvider(groq_client, groq_settings)

    with pytest.raises(ProviderBadResponseError):
        await provider.suggest(HINDI, said("मुझे समय चाहिए"))


@respx.mock
async def test_items_missing_either_side_are_skipped(groq_client, groq_settings):
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=completion(
            '{"items": [{"original": "समय"}, {"english": "time"}, "junk",'
            ' {"original": "जिम्मेदारी", "english": "responsibility"}]}'
        )
    )
    provider = GroqEnglishAlternativesProvider(groq_client, groq_settings)

    items = await provider.suggest(HINDI, said("मुझे जिम्मेदारी चाहिए"))

    assert [i.english for i in items] == ["responsibility"]


@respx.mock
async def test_a_bridge_conversation_is_pinned_to_its_language_on_the_full_model(
    groq_client, groq_settings
):
    route = respx.post(f"{BASE_URL}/audio/transcriptions").mock(
        return_value=httpx.Response(200, json={"text": "नमस्ते", "language": "hindi"})
    )
    provider = GroqSpeechToTextProvider(groq_client, groq_settings)

    await provider.transcribe(b"wav", "a.wav", "audio/wav", language="hi")

    sent = route.calls.last.request.content
    assert b'name="language"' in sent and b"\r\n\r\nhi\r\n" in sent
    assert b"whisper-large-v3\r\n" in sent
    assert b"turbo" not in sent


@respx.mock
async def test_an_english_turn_keeps_the_english_pin_and_the_original_model(
    groq_client, groq_settings
):
    route = respx.post(f"{BASE_URL}/audio/transcriptions").mock(
        return_value=httpx.Response(200, json={"text": "Hello", "language": "english"})
    )
    provider = GroqSpeechToTextProvider(groq_client, groq_settings)

    await provider.transcribe(b"wav", "a.wav", "audio/wav")

    sent = route.calls.last.request.content
    assert b"\r\n\r\nen\r\n" in sent
    assert b"whisper-large-v3-turbo" in sent


def test_a_whole_clause_is_not_reported_as_a_phrase():
    clause = "आज मैं ऑफिस में बहुत ज्यादा काम करके घर वापस आया"
    items = clean([alt(clause, "I came home after a lot of work")], said(clause))

    assert items == []


def test_the_prompt_asks_for_the_shortest_span_not_the_sentence():
    from app.providers.groq.alternatives import _prompt_for

    prompt = _prompt_for(get_language("ta"))

    assert "SHORTEST span" in prompt
    assert "Never a whole sentence or clause" in prompt
    assert "first person" in prompt
    assert "a wrong English word is worse than a missing one" in prompt.replace(
        "\n", " "
    ).replace("  ", " ")


async def test_concurrent_reruns_leave_one_report_not_the_union(sql_repository):
    """Two requests re-running the same report at once. Each used to delete
    the rows it had loaded and insert its own, so the second delete matched
    nothing (the first had already removed them) and both sets survived."""
    await sql_repository.save(make_analysis("s1", alt("पुराना", "old")))

    await asyncio.gather(
        *[
            sql_repository.save(
                make_analysis(
                    "s1", alt(f"पहला{n}", f"first {n}"), alt(f"दूसरा{n}", f"second {n}")
                )
            )
            for n in range(4)
        ]
    )

    loaded = await sql_repository.get("s1")
    assert len(loaded.items) == 2
    assert len({item.english.split()[1] for item in loaded.items}) == 1
