"""
Hallucination prevention — RAG_SYSTEM.md §9's five-layer defense. Layers 2
(citation/entailment verification) and 3 (numeric strict-matching) need a
*claim* to check -- text asserting a fact -- which only exists once
something has generated an answer. This service builds the verification
tools (real, local models -- no LLM API call required) that the future AI
Copilot will call once it generates a claim; layers 4 (low-confidence
refusal) and 5 (conflicting-source detection) run here, now, on the
retrieval/re-rank result itself, with no generation step needed at all.

Real local NLI model, not an LLM call: `cross-encoder/nli-deberta-v3-base`
is a genuine pretrained natural-language-inference classifier (entailment /
neutral / contradiction), exactly what §8.3 specifies -- it requires no API
key and runs entirely locally, unlike the free-text generation step itself.
"""

from __future__ import annotations

import re

import structlog

logger = structlog.get_logger(__name__)

MIN_CONFIDENCE_THRESHOLD = 0.05  # layer 4: below this top re-rank score, refuse rather than answer
NLI_MODEL = "cross-encoder/nli-deberta-v3-base"

_NUMERIC_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(%|percent|bar|psi|days?|hours?|minutes?|°?\s?c\b|celsius|lel|kg|mm|rpm)", re.IGNORECASE
)


def should_refuse(top_score: float | None, top_raw_score: float | None = None) -> tuple[bool, str | None]:
    """Layer 4. Returns (should_refuse, reason).

    Checks the final (graph-boosted) score AND the raw cross-encoder score
    independently, not just the boosted one -- the graph-aware boost (§7.2,
    reranking.py) adds a flat +0.15 to any graph-linked candidate regardless
    of how semantically irrelevant its text actually is, so a candidate whose
    real relevance is at or near zero could otherwise clear the confidence
    gate purely by being graph-linked. Requiring the pre-boost score to also
    clear the bar keeps a topical-but-ungrounded graph connection from being
    read as evidence of relevance."""
    if top_score is None:
        return True, "no candidate chunks passed retrieval"
    if top_score < MIN_CONFIDENCE_THRESHOLD:
        return True, f"top re-ranked relevance score ({top_score:.3f}) is below the minimum confidence threshold"
    if top_raw_score is not None and top_raw_score < MIN_CONFIDENCE_THRESHOLD:
        return True, f"top raw (pre-graph-boost) relevance score ({top_raw_score:.3f}) is below the minimum confidence threshold"
    return False, None


def extract_numeric_claims(text: str) -> list[tuple[float, str]]:
    return [(float(value), unit.strip().lower()) for value, unit in _NUMERIC_RE.findall(text)]


TOPICAL_SIMILARITY_THRESHOLD = 0.4  # filters clearly-unrelated text; see docstring for what it can't filter


def detect_numeric_conflicts(chunks: list[dict]) -> list[dict]:
    """Layer 5, numeric-claim variant: two currently-effective chunks that
    state a different numeric value for what appears to be the same unit
    of measure are flagged as a possible conflict -- a real, if narrower,
    implementation of §9 layer 5 that needs no NLI/LLM judgment call, only
    unit-matching arithmetic, which is exactly where a paraphrase-blind
    semantic check would be the wrong tool (§8.4's own reasoning, reapplied
    at the cross-source level instead of the single-claim level).

    The embedding cosine similarity already computed for hybrid search
    (retrieval.py) is used as a topical-relevance gate, to at least exclude
    genuinely unrelated chunks (measured empirically against this corpus: an
    unrelated pair sits at roughly -0.05 to 0.10 cosine similarity, so 0.4 is
    a comfortable margin above that noise floor).

    Known, disclosed limitation, not silently papered over: this gate cannot
    distinguish "genuinely the same requirement" from "independently-written
    regulatory text using the same instructional template" -- "fixed fire
    suppression systems shall be inspected at intervals not exceeding 180
    days" and "every fixed gas detector shall be functionally tested at
    intervals not exceeding 90 days" measure at 0.70 cosine similarity
    despite governing entirely different equipment, because standards bodies
    write in a shared phrasing convention this embedding model reads as
    topical closeness. Reliably telling those apart needs subject-entity
    extraction ("fire suppression system" vs. "gas detector") that this pass
    does not implement -- which is exactly why §9 layer 5 specifies
    *surfacing* a detected conflict for human judgment rather than silently
    auto-resolving it: a Safety Officer looking at both citations side by
    side recognizes an unrelated-equipment false positive in seconds, which
    is the intended failure mode here, not a bug to hide."""
    claims_by_chunk = [
        (chunk["chunk"], extract_numeric_claims(chunk["chunk"].text)) for chunk in chunks
    ]
    conflicts = []
    for i in range(len(claims_by_chunk)):
        chunk_a, claims_a = claims_by_chunk[i]
        for j in range(i + 1, len(claims_by_chunk)):
            chunk_b, claims_b = claims_by_chunk[j]
            if chunk_a.embedding is not None and chunk_b.embedding is not None:
                from app.rag.store import cosine_similarity

                if cosine_similarity(chunk_a.embedding, chunk_b.embedding) < TOPICAL_SIMILARITY_THRESHOLD:
                    continue
            for value_a, unit_a in claims_a:
                for value_b, unit_b in claims_b:
                    if unit_a == unit_b and value_a != value_b:
                        conflicts.append(
                            {
                                "unit": unit_a,
                                "chunk_a": {"chunk_id": chunk_a.metadata.chunk_id, "citation": chunk_a.metadata.citation_template, "value": value_a},
                                "chunk_b": {"chunk_id": chunk_b.metadata.chunk_id, "citation": chunk_b.metadata.citation_template, "value": value_b},
                            }
                        )
    return conflicts


class NliChecker:
    """§8.3's textual-entailment check -- does a cited chunk's text entail a
    specific claim, not merely relate to it topically."""

    def __init__(self, model_name: str = NLI_MODEL) -> None:
        self._model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("nli_model_loading", model=self._model_name)
            self._model = CrossEncoder(self._model_name)
            logger.info("nli_model_loaded", model=self._model_name)
        return self._model

    def warm_up(self) -> None:
        self._get_model()

    def check_entailment(self, premise_chunk_text: str, claim: str) -> dict:
        model = self._get_model()
        scores = model.predict([[premise_chunk_text, claim]])[0]
        # cross-encoder/nli-deberta-v3-base label order: contradiction, entailment, neutral
        labels = ["contradiction", "entailment", "neutral"]
        probs = _softmax(scores)
        result = dict(zip(labels, [float(p) for p in probs]))
        result["predicted_label"] = labels[int(scores.argmax())]
        return result


def _softmax(scores):
    import numpy as np

    exp = np.exp(scores - np.max(scores))
    return exp / exp.sum()


nli_checker = NliChecker()


def verify_claim(*, claim: str, cited_chunk_id: str, retrieved_chunks: list[dict]) -> dict:
    """The two independent checks §8.3 specifies, run together for one claim
    citing one chunk: (1) citation existence, (2) textual entailment (or
    §8.4's stricter numeric near-exact match, when the claim is quantitative)."""
    by_id = {c["chunk"].metadata.chunk_id: c["chunk"] for c in retrieved_chunks}
    if cited_chunk_id not in by_id:
        return {"verified": False, "reason": "cited_chunk_not_in_retrieved_set"}

    source_text = by_id[cited_chunk_id].text
    claim_numbers = extract_numeric_claims(claim)

    if claim_numbers:
        source_numbers = extract_numeric_claims(source_text)
        for value, unit in claim_numbers:
            if not any(unit == su and abs(value - sv) < 1e-9 for sv, su in source_numbers):
                return {"verified": False, "reason": "numeric_claim_does_not_exactly_match_source", "claimed": {"value": value, "unit": unit}}
        return {"verified": True, "reason": "numeric_exact_match"}

    entailment = nli_checker.check_entailment(source_text, claim)
    verified = entailment["predicted_label"] == "entailment"
    return {"verified": verified, "reason": f"nli_{entailment['predicted_label']}", "entailment": entailment}
