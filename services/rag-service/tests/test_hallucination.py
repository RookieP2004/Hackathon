from datetime import datetime, timezone

from app.rag.hallucination import detect_numeric_conflicts, extract_numeric_claims, should_refuse
from app.rag.schema import Chunk, ChunkMetadata


def _metadata(chunk_id: str, **overrides) -> ChunkMetadata:
    defaults = dict(
        chunk_id=chunk_id, document_id=1, document_class="oisd", authority="regulatory",
        version=None, effective_date=None, superseded_at=None, section_reference=None,
        equipment_type_scope=None, hazard_class_scope=None, jurisdiction=None, graph_node_id=None,
        access_classification="standard", ocr_confidence=None, citation_template="Test Citation",
    )
    defaults.update(overrides)
    return ChunkMetadata(**defaults)


def test_extract_numeric_claims_finds_value_and_unit():
    claims = extract_numeric_claims("the inspection interval is 180 days and the alarm is set at 10 percent LEL")
    assert (180.0, "days") in claims
    assert (10.0, "percent") in claims


def test_should_refuse_below_threshold():
    refuse, reason = should_refuse(0.01)
    assert refuse is True
    assert "confidence" in reason


def test_should_not_refuse_above_threshold():
    refuse, reason = should_refuse(0.9)
    assert refuse is False
    assert reason is None


def test_should_refuse_when_no_candidates():
    refuse, reason = should_refuse(None)
    assert refuse is True


def test_should_refuse_when_graph_boost_masks_a_low_raw_score():
    # boosted score (0.15 raw + 0.15 GRAPH_BOOST) clears the threshold on its own,
    # but the raw pre-boost relevance is near zero -- a graph link should not be
    # able to launder an otherwise-irrelevant chunk past the confidence gate.
    refuse, reason = should_refuse(0.30, 0.01)
    assert refuse is True
    assert "raw" in reason


def test_should_not_refuse_when_both_raw_and_boosted_scores_clear_threshold():
    refuse, reason = should_refuse(0.9, 0.8)
    assert refuse is False
    assert reason is None


def test_detect_numeric_conflicts_flags_disagreeing_values():
    chunk_a = Chunk(text="the inspection interval is 90 days", metadata=_metadata("c1"))
    chunk_b = Chunk(text="the inspection interval is 180 days", metadata=_metadata("c2"))
    conflicts = detect_numeric_conflicts([{"chunk": chunk_a}, {"chunk": chunk_b}])
    assert len(conflicts) == 1
    assert conflicts[0]["unit"] == "days"


def test_detect_numeric_conflicts_no_conflict_when_values_agree():
    chunk_a = Chunk(text="the inspection interval is 90 days", metadata=_metadata("c1"))
    chunk_b = Chunk(text="servicing is required every 90 days", metadata=_metadata("c2"))
    conflicts = detect_numeric_conflicts([{"chunk": chunk_a}, {"chunk": chunk_b}])
    assert conflicts == []
