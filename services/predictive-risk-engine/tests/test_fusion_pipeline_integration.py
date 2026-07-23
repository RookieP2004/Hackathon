"""
Full end-to-end integration: real Postgres (V-12/RV-9/R-3, Zone 3 -- the
same equipment RISK_FUSION_ENGINE.md §5's worked example narrates), the real
knowledge-graph service (graph-constrained candidate generation), and the
real computer-vision service (live vision signal), run against the actual
`assess_equipment` pipeline -- not mocked.
"""

import asyncpg
import pytest

from aegis_api_common import ServiceActorTokenMinter

from app.fusion.pipeline import assess_equipment
from app.fusion.simulator import SensorSimulator

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
KNOWLEDGE_GRAPH_URL = "http://localhost:8007"
COMPUTER_VISION_URL = "http://localhost:8004"
TOKEN_MINTER = ServiceActorTokenMinter(
    postgres_dsn=POSTGRES_DSN, jwt_secret="changeme_generate_a_real_secret_before_any_shared_deployment", jwt_algorithm="HS256",
)

V12_EQUIPMENT_ID = 2
GS14_SENSOR_ID = 1
PT22_SENSOR_ID = 2
CLUSTER_SENSOR_IDS = [1, 2, 3, 4, 5, 6, 43, 44, 45, 46, 83, 84, 85, 86]  # V-12/RV-9/R-3/PIPE-12A cluster


@pytest.fixture(autouse=True)
async def _clean_cluster_sensor_readings():
    """Every test in this file writes real rows into `sensor_readings` for
    the V-12 cluster and none of them clean up after themselves -- across
    repeated runs, a later test's "leading baseline" window silently
    included an earlier test's leftover escalated tail (confirmed
    empirically: this exact contamination made a genuinely 25x gas spike
    normalize to a mid-range, unremarkable value). Clearing before every
    test keeps each one's history genuinely self-contained."""
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        await conn.execute("DELETE FROM sensor_readings WHERE sensor_id = ANY($1::bigint[])", CLUSTER_SENSOR_IDS)
    finally:
        await conn.close()
    yield


@pytest.fixture
async def warmed_up_simulator():
    """Ticks the simulator several times first so admitted sensors have real
    history to compute normalized values / temporal features from -- a
    single reading can't demonstrate deviation-from-baseline at all."""
    simulator = SensorSimulator()
    await simulator.load_sensors(POSTGRES_DSN)
    for _ in range(8):
        await simulator.tick_and_persist(POSTGRES_DSN)
    return simulator


async def test_assess_equipment_returns_all_five_hazard_classes(warmed_up_simulator):
    bundles = await assess_equipment(
        equipment_id=V12_EQUIPMENT_ID, postgres_dsn=POSTGRES_DSN,
        knowledge_graph_url=KNOWLEDGE_GRAPH_URL, computer_vision_url=COMPUTER_VISION_URL, token_minter=TOKEN_MINTER,
    )
    hazard_classes = {b["hazard_class"] for b in bundles}
    assert hazard_classes == {"fire", "explosion", "gas_leak", "worker_injury", "machine_failure"}
    for bundle in bundles:
        assert 0 <= bundle["score"] <= 100
        assert bundle["severity"] in ("low", "medium", "high", "critical")
        assert bundle["gate_structure_version"] == "risk-fusion-v1"


async def test_assess_equipment_uses_real_graph_admitted_sensors(warmed_up_simulator):
    bundles = await assess_equipment(
        equipment_id=V12_EQUIPMENT_ID, postgres_dsn=POSTGRES_DSN,
        knowledge_graph_url=KNOWLEDGE_GRAPH_URL, computer_vision_url=COMPUTER_VISION_URL, token_minter=TOKEN_MINTER,
    )
    explosion = next(b for b in bundles if b["hazard_class"] == "explosion")
    evidence_node_ids = {f["evidence_node_id"] for f in explosion["contributing_factors"]}
    # V-12's own graph-admitted sensors (GS-14 gas, PT-22 pressure) should be feeding the Fuel-in-Range sub-condition.
    assert "fuel_gas" in evidence_node_ids or "fuel_pressure" in evidence_node_ids


async def test_assess_equipment_writes_real_risk_score_rows(warmed_up_simulator):
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        before = await conn.fetchval(
            "SELECT count(*) FROM risk_scores WHERE equipment_id = $1 AND model_version LIKE 'risk-fusion:%'", V12_EQUIPMENT_ID
        )
    finally:
        await conn.close()

    await assess_equipment(
        equipment_id=V12_EQUIPMENT_ID, postgres_dsn=POSTGRES_DSN,
        knowledge_graph_url=KNOWLEDGE_GRAPH_URL, computer_vision_url=COMPUTER_VISION_URL, token_minter=TOKEN_MINTER,
    )

    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        after = await conn.fetchval(
            "SELECT count(*) FROM risk_scores WHERE equipment_id = $1 AND model_version LIKE 'risk-fusion:%'", V12_EQUIPMENT_ID
        )
    finally:
        await conn.close()
    assert after == before + 5  # one row per hazard class


async def test_assess_equipment_anchors_risk_nodes_into_neo4j(warmed_up_simulator):
    from neo4j import AsyncGraphDatabase

    await assess_equipment(
        equipment_id=V12_EQUIPMENT_ID, postgres_dsn=POSTGRES_DSN,
        knowledge_graph_url=KNOWLEDGE_GRAPH_URL, computer_vision_url=COMPUTER_VISION_URL, token_minter=TOKEN_MINTER,
    )

    driver = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "changeme_local_only"))
    try:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (r:Risk)-[:ASSESSES]->(eq:Equipment {id: $id}) RETURN count(r) AS c", id=V12_EQUIPMENT_ID
            )
            record = await result.single()
    finally:
        await driver.close()
    assert record["c"] > 0


async def test_assess_unknown_equipment_raises_value_error():
    with pytest.raises(ValueError):
        await assess_equipment(
            equipment_id=999999, postgres_dsn=POSTGRES_DSN,
            knowledge_graph_url=KNOWLEDGE_GRAPH_URL, computer_vision_url=COMPUTER_VISION_URL, token_minter=TOKEN_MINTER,
        )


async def test_explosion_precursor_injection_raises_fuel_in_range_subcondition():
    """§4.2's noisy-AND means injecting *only* Fuel-in-Range evidence (gas +
    pressure) correctly should NOT necessarily raise the overall, jointly-
    gated explosion score -- a near-absent Ignition Source or Confinement
    signal legitimately caps the joint probability regardless (this is the
    network behaving exactly as designed, confirmed by first writing this
    test to assert the joint score itself and finding it stayed capped near
    zero even under a 25x gas escalation, exactly matching §4.2's own stated
    intent that "the absence of any one factor caps the network's output
    regardless of how strongly the other two are indicated"). What a fuel-
    only injection *should* move is the Fuel-in-Range sub-condition itself,
    which is what this test actually checks."""
    baseline_simulator = SensorSimulator()
    await baseline_simulator.load_sensors(POSTGRES_DSN)
    for _ in range(8):
        await baseline_simulator.tick_and_persist(POSTGRES_DSN)
    baseline_bundles = await assess_equipment(
        equipment_id=V12_EQUIPMENT_ID, postgres_dsn=POSTGRES_DSN,
        knowledge_graph_url=KNOWLEDGE_GRAPH_URL, computer_vision_url=COMPUTER_VISION_URL, token_minter=TOKEN_MINTER, anchor_to_graph=False,
    )
    baseline_fuel = next(b for b in baseline_bundles if b["hazard_class"] == "explosion")["sub_condition_probabilities"]["fuel_in_range"]

    escalating_simulator = SensorSimulator()
    await escalating_simulator.load_sensors(POSTGRES_DSN)
    for _ in range(15):
        await escalating_simulator.tick_and_persist(POSTGRES_DSN)  # genuine normal baseline first
    escalating_simulator.inject_precursor_pattern(GS14_SENSOR_ID, target=5000.0, rate=0.4)
    escalating_simulator.inject_precursor_pattern(PT22_SENSOR_ID, target=40.0, rate=0.4)
    for _ in range(10):
        await escalating_simulator.tick_and_persist(POSTGRES_DSN)  # then the escalation itself

    escalated_bundles = await assess_equipment(
        equipment_id=V12_EQUIPMENT_ID, postgres_dsn=POSTGRES_DSN,
        knowledge_graph_url=KNOWLEDGE_GRAPH_URL, computer_vision_url=COMPUTER_VISION_URL, token_minter=TOKEN_MINTER, anchor_to_graph=False,
    )
    escalated_explosion = next(b for b in escalated_bundles if b["hazard_class"] == "explosion")
    escalated_fuel = escalated_explosion["sub_condition_probabilities"]["fuel_in_range"]

    # Verified empirically: gas normalizes to 1.0 (sigmoid-saturated, LR ~20) and
    # pressure to 1.0 (LR ~6.5) under this injection, moving fuel_in_range from a
    # baseline around 0.04 to around 0.09-0.10 against explosion's deliberately
    # tiny 0.0008 prior (§5's own worked example reaches only ~32% posterior
    # after two comparable corroborating signals against that same prior -- a
    # much higher bar here would contradict the spec's own math, not confirm it).
    assert escalated_fuel > baseline_fuel * 1.5
    assert escalated_fuel > 0.08
    # The joint (noisy-AND) score stays capped since ignition/confinement weren't also escalated --
    # asserting this explicitly documents the behavior as intentional, not an unverified assumption.
    assert escalated_explosion["score"] < 5.0
