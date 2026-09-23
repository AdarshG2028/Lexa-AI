"""The one bug this file exists to pin down: two analyses for the same
session, saved close together, used to race to create that session's row -
the loser hit a UNIQUE constraint violation and surfaced as "the analysis
could not be saved" even though the winner's write succeeded. Reproduced
here with a real SQLite database, since the race is in SQL commit ordering,
not in application logic a mock could exercise.
"""

import asyncio

import pytest

from app.analysis.sql import SqlAnalysisRepository
from app.db.engine import create_engine, create_session_factory, create_tables
from app.models import FluencyAnalysis, GrammarAnalysis, VocabularyAnalysis


@pytest.fixture
async def repository(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await create_tables(engine)
    yield SqlAnalysisRepository(create_session_factory(engine))
    await engine.dispose()


def make_fluency(session_id: str) -> FluencyAnalysis:
    return FluencyAnalysis(
        session_id=session_id,
        timed_words=42,
        analyzed_seconds=20.0,
        speaking_rate_wpm=126.0,
        articulation_rate_wpm=130.0,
        pause_count=2,
        long_pause_count=0,
        total_pause_seconds=1.0,
        filler_count=1,
        repetition_count=0,
        restart_count=0,
        fluency_score=88,
    )


def make_grammar(session_id: str) -> GrammarAnalysis:
    return GrammarAnalysis(
        session_id=session_id,
        provider="groq",
        sentences_analyzed=3,
        words_analyzed=30,
        grammar_score=90,
    )


def make_vocabulary(session_id: str) -> VocabularyAnalysis:
    return VocabularyAnalysis(
        session_id=session_id,
        provider="groq",
        words_analyzed=30,
        unique_words=22,
        lexical_diversity=0.73,
        vocabulary_score=85,
    )


async def test_two_sections_saved_concurrently_for_a_new_session_both_succeed(
    repository,
):
    session_id = "concurrent-session"

    await asyncio.gather(
        repository.save_fluency(make_fluency(session_id)),
        repository.save_grammar(make_grammar(session_id)),
    )

    fluency = await repository.get_fluency(session_id)
    grammar = await repository.get_grammar(session_id)
    assert fluency is not None and fluency.fluency_score == 88
    assert grammar is not None and grammar.grammar_score == 90


async def test_three_sections_saved_concurrently_all_land(repository):
    """The real shape of the bug: the report page runs all three analyses,
    and a page refresh mid-run can start a second batch overlapping the
    first - more than two writers racing for the same new row."""
    session_id = "three-way-session"

    await asyncio.gather(
        repository.save_fluency(make_fluency(session_id)),
        repository.save_grammar(make_grammar(session_id)),
        repository.save_vocabulary(make_vocabulary(session_id)),
    )

    assert (await repository.get_fluency(session_id)) is not None
    assert (await repository.get_grammar(session_id)) is not None
    assert (await repository.get_vocabulary(session_id)) is not None


async def test_saving_the_same_section_twice_keeps_the_later_values(repository):
    """Not a race between different sections - the same section saved again
    (a genuine refresh re-running an already-finished analysis) must update
    in place, not fail or duplicate the row."""
    session_id = "resaved-session"

    await repository.save_grammar(make_grammar(session_id))
    updated = make_grammar(session_id)
    updated.grammar_score = 40
    await repository.save_grammar(updated)

    grammar = await repository.get_grammar(session_id)
    assert grammar is not None
    assert grammar.grammar_score == 40
