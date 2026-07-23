import asyncpg
import pytest

from aegis_agents.memory import AgentMemory, ensure_agent_memory_tables

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
TEST_AGENT_ID = "zztest-memory-agent"


@pytest.fixture(autouse=True)
async def _clean_test_agent_rows():
    await ensure_agent_memory_tables(POSTGRES_DSN)
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        await conn.execute("DELETE FROM agent_decision_log WHERE agent_id = $1", TEST_AGENT_ID)
        await conn.execute("DELETE FROM agent_episodic_memory WHERE agent_id = $1", TEST_AGENT_ID)
    finally:
        await conn.close()
    yield


@pytest.fixture
def memory():
    return AgentMemory(POSTGRES_DSN, TEST_AGENT_ID, "v1")


async def test_log_decision_persists_a_real_row(memory):
    decision_id = await memory.log_decision(
        decision="raise_assertion", reasoning="gas reading exceeded baseline by 4 std", confidence=0.9,
        evidence_refs=["sensor:1"], correlation_id="corr-1",
    )
    decisions = await memory.recent_decisions(limit=5)
    assert any(d.id == decision_id for d in decisions)
    match = next(d for d in decisions if d.id == decision_id)
    assert match.reasoning == "gas reading exceeded baseline by 4 std"
    assert match.confidence == pytest.approx(0.9)
    assert match.evidence_refs == ["sensor:1"]


async def test_explain_returns_the_original_reasoning_verbatim(memory):
    decision_id = await memory.log_decision(decision="escalate", reasoning="two independent signals corroborate", confidence=0.8, evidence_refs=[])
    explanation = await memory.explain(decision_id)
    assert explanation == "two independent signals corroborate"


async def test_explain_returns_none_for_unknown_decision(memory):
    assert await memory.explain(999999999) is None


async def test_remember_episode_and_record_outcome(memory):
    episode_id = await memory.remember_episode(kind="assertion", payload={"foo": "bar"})
    await memory.record_outcome(episode_id, outcome="confirmed_true_positive")

    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        row = await conn.fetchrow("SELECT outcome, outcome_recorded_at FROM agent_episodic_memory WHERE id = $1", episode_id)
    finally:
        await conn.close()
    assert row["outcome"] == "confirmed_true_positive"
    assert row["outcome_recorded_at"] is not None


async def test_recent_decisions_ordered_newest_first(memory):
    await memory.log_decision(decision="d1", reasoning="first", confidence=0.5, evidence_refs=[])
    await memory.log_decision(decision="d2", reasoning="second", confidence=0.6, evidence_refs=[])
    decisions = await memory.recent_decisions(limit=5)
    assert decisions[0].decision == "d2"
    assert decisions[1].decision == "d1"
