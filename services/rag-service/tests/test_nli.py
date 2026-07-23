from app.rag.hallucination import nli_checker, verify_claim
from app.rag.schema import Chunk, ChunkMetadata


def _metadata(chunk_id: str) -> ChunkMetadata:
    return ChunkMetadata(
        chunk_id=chunk_id, document_id=1, document_class="oisd", authority="regulatory",
        version=None, effective_date=None, superseded_at=None, section_reference=None,
        equipment_type_scope=None, hazard_class_scope=None, jurisdiction=None, graph_node_id=None,
        access_classification="standard", ocr_confidence=None, citation_template="Test Citation",
    )


def test_real_nli_model_recognizes_entailment():
    result = nli_checker.check_entailment(
        "fixed fire suppression systems shall be inspected at intervals not exceeding 180 days",
        "the inspection interval for fire suppression systems is 180 days",
    )
    assert result["predicted_label"] == "entailment"


def test_real_nli_model_recognizes_contradiction():
    result = nli_checker.check_entailment(
        "fixed fire suppression systems shall be inspected at intervals not exceeding 180 days",
        "fire suppression systems require no periodic inspection at all",
    )
    assert result["predicted_label"] == "contradiction"


def test_verify_claim_rejects_uncited_chunk():
    chunk = Chunk(text="some source text", metadata=_metadata("c1"))
    result = verify_claim(claim="a claim", cited_chunk_id="not_in_set", retrieved_chunks=[{"chunk": chunk}])
    assert result["verified"] is False
    assert result["reason"] == "cited_chunk_not_in_retrieved_set"


def test_verify_claim_numeric_exact_match_required():
    chunk = Chunk(text="the inspection interval is 90 days", metadata=_metadata("c1"))
    ok = verify_claim(claim="the interval is 90 days", cited_chunk_id="c1", retrieved_chunks=[{"chunk": chunk}])
    assert ok["verified"] is True

    wrong = verify_claim(claim="the interval is 60 days", cited_chunk_id="c1", retrieved_chunks=[{"chunk": chunk}])
    assert wrong["verified"] is False
    assert wrong["reason"] == "numeric_claim_does_not_exactly_match_source"
