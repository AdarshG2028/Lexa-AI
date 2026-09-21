"""Both session stores must behave identically.

The conversation service is written against the `SessionRepository` protocol,
so the same contract is run against the in-memory and the database
implementations. If the database store diverges, this is where it shows.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.db.engine import create_engine, create_session_factory, create_tables
from app.models import AudioRef, Session, SessionStatus, Speaker, Turn
from app.sessions.memory import InMemorySessionRepository
from app.sessions.sql import SqlSessionRepository


@pytest.fixture
async def sql_repository(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await create_tables(engine)
    yield SqlSessionRepository(create_session_factory(engine))
    await engine.dispose()


@pytest.fixture
def memory_repository():
    return InMemorySessionRepository()


@pytest.fixture(params=["memory", "database"])
async def repository(request, memory_repository, sql_repository):
    return memory_repository if request.param == "memory" else sql_repository


def make_turn(index: int, said: str, replied: str | None = None) -> Turn:
    return Turn(
        index=index,
        speaker=Speaker.USER,
        transcript=said,
        assistant_response=replied,
        user_audio=AudioRef(
            key=f"s/{index}-user.wav", format="wav",
            duration_seconds=1.5, size_bytes=4096,
        ),
        assistant_audio=AudioRef(key=f"s/{index}-ai.wav", format="wav"),
    )


async def test_a_created_session_can_be_read_back(repository):
    created = await repository.create(Session(user_id="adarsh"))
    loaded = await repository.get(created.id)

    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.user_id == "adarsh"
    assert loaded.status is SessionStatus.ACTIVE
    assert loaded.turns == []


async def test_an_unknown_session_reads_as_none(repository):
    assert await repository.get("no-such-id") is None


async def test_turns_are_persisted_with_their_content(repository):
    session = await repository.create(Session())
    session.turns.append(make_turn(0, "I go to college", "Which college?"))
    await repository.save(session)

    loaded = await repository.get(session.id)
    turn = loaded.turns[0]

    assert turn.transcript == "I go to college"
    assert turn.assistant_response == "Which college?"
    assert turn.speaker is Speaker.USER
    assert turn.index == 0


async def test_audio_references_survive_a_round_trip(repository):
    """Phases 6 and 7 analyse the stored user audio, so its reference and
    duration must come back intact."""
    session = await repository.create(Session())
    session.turns.append(make_turn(0, "hello", "hi"))
    await repository.save(session)

    turn = (await repository.get(session.id)).turns[0]

    assert turn.user_audio.key == "s/0-user.wav"
    assert turn.user_audio.duration_seconds == 1.5
    assert turn.user_audio.size_bytes == 4096
    assert turn.assistant_audio.key == "s/0-ai.wav"
    assert turn.assistant_audio.duration_seconds is None


async def test_turns_keep_their_order_across_many_saves(repository):
    session = await repository.create(Session())
    for i in range(5):
        session.turns.append(make_turn(i, f"said {i}", f"replied {i}"))
        await repository.save(session)

    loaded = await repository.get(session.id)

    assert [t.index for t in loaded.turns] == [0, 1, 2, 3, 4]
    assert [t.transcript for t in loaded.turns] == [f"said {i}" for i in range(5)]


async def test_saving_repeatedly_does_not_duplicate_turns(repository):
    session = await repository.create(Session())
    session.turns.append(make_turn(0, "once"))

    await repository.save(session)
    await repository.save(session)
    await repository.save(session)

    assert len((await repository.get(session.id)).turns) == 1


async def test_status_and_end_time_are_updated(repository):
    session = await repository.create(Session())
    ended = datetime.now(timezone.utc)
    session.status = SessionStatus.COMPLETED
    session.ended_at = ended
    await repository.save(session)

    loaded = await repository.get(session.id)

    assert loaded.status is SessionStatus.COMPLETED
    assert loaded.ended_at is not None
    assert abs((loaded.ended_at - ended).total_seconds()) < 1


async def test_timestamps_come_back_timezone_aware(repository):
    """A naive datetime here would crash the session idle check, which
    compares against an aware `now`."""
    session = await repository.create(Session())
    loaded = await repository.get(session.id)

    assert loaded.started_at.tzinfo is not None
    assert loaded.last_activity_at.tzinfo is not None
    assert loaded.idle_seconds() >= 0


async def test_last_activity_is_persisted(repository):
    session = await repository.create(Session())
    moment = datetime.now(timezone.utc) - timedelta(minutes=42)
    session.last_activity_at = moment
    await repository.save(session)

    loaded = await repository.get(session.id)
    assert abs((loaded.last_activity_at - moment).total_seconds()) < 1


async def test_sessions_are_isolated_from_each_other(repository):
    first = await repository.create(Session())
    second = await repository.create(Session())
    first.turns.append(make_turn(0, "belongs to first"))
    await repository.save(first)

    assert (await repository.get(second.id)).turns == []


async def test_saving_a_session_that_was_never_created_still_stores_it(repository):
    session = Session()
    session.turns.append(make_turn(0, "orphan"))
    await repository.save(session)

    assert (await repository.get(session.id)).turns[0].transcript == "orphan"


async def test_database_survives_losing_the_repository_instance(tmp_path):
    """The point of Phase 3: a restart must not lose the conversation."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'restart.db'}"

    engine = create_engine(url)
    await create_tables(engine)
    repository = SqlSessionRepository(create_session_factory(engine))
    session = await repository.create(Session(user_id="adarsh"))
    session.turns.append(make_turn(0, "before the restart", "noted"))
    await repository.save(session)
    await engine.dispose()

    reopened = create_engine(url)
    revived = SqlSessionRepository(create_session_factory(reopened))
    loaded = await revived.get(session.id)
    await reopened.dispose()

    assert loaded.user_id == "adarsh"
    assert loaded.turns[0].transcript == "before the restart"
    assert loaded.turns[0].assistant_response == "noted"
