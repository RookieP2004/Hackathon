"""
Re-ranking — RAG_SYSTEM.md §7. Hybrid search's fused RRF score is a
bi-encoder-grade signal; a real cross-encoder (jointly encoding query and
each candidate) re-scores the top-K and that second-pass score determines
final ranking (§7.1). Three further adjustments apply on top, in order:
graph-aware boost (§7.2), diversity-aware penalty (§7.3), and a
recency/version-aware penalty (§7.4).
"""

from __future__ import annotations

import structlog

from app.rag.retrieval import RetrievalCandidate
from app.rag.store import tokenize

logger = structlog.get_logger(__name__)

CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

GRAPH_BOOST = 0.15
SUPERSEDED_PENALTY = 0.25
DIVERSITY_PENALTY_THRESHOLD = 0.6  # Jaccard token overlap above which two chunks count as near-duplicates
DIVERSITY_PENALTY = 0.2


class CrossEncoderReranker:
    def __init__(self, model_name: str = CROSS_ENCODER_MODEL) -> None:
        self._model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("cross_encoder_loading", model=self._model_name)
            self._model = CrossEncoder(self._model_name)
            logger.info("cross_encoder_loaded", model=self._model_name)
        return self._model

    def warm_up(self) -> None:
        self._get_model()

    def score(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        model = self._get_model()
        pairs = [[query, text] for text in texts]
        return [float(s) for s in model.predict(pairs)]


cross_encoder = CrossEncoderReranker()


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _sigmoid(x: float) -> float:
    import math

    return 1.0 / (1.0 + math.exp(-x))


def rerank(query: str, candidates: list[RetrievalCandidate], top_n: int = 10) -> list[dict]:
    if not candidates:
        return []

    texts = [c.chunk.text for c in candidates]
    # ms-marco-MiniLM-L-6-v2 outputs unbounded logits, not probabilities -- its own
    # model card recommends a sigmoid to get a relevance score in [0, 1], which is
    # what makes hallucination.py's MIN_CONFIDENCE_THRESHOLD a meaningful comparison
    # rather than an arbitrary cutoff against an unbounded, sign-ambiguous scale.
    cross_scores = [_sigmoid(s) for s in cross_encoder.score(query, texts)]

    scored = []
    for candidate, base_score in zip(candidates, cross_scores):
        score = base_score
        if candidate.graph_linked:
            score += GRAPH_BOOST  # §7.2
        if candidate.chunk.metadata.superseded_at is not None:
            score -= SUPERSEDED_PENALTY  # §7.4
        scored.append({"candidate": candidate, "score": score, "raw_score": base_score})

    scored.sort(key=lambda s: s["score"], reverse=True)

    # §7.3: diversity-aware selection -- penalize (and reorder past) a candidate
    # that is a near-duplicate of an already-selected higher-ranked one.
    selected: list[dict] = []
    token_sets = {id(s["candidate"]): set(tokenize(s["candidate"].chunk.text)) for s in scored}
    remaining = list(scored)
    while remaining and len(selected) < top_n:
        best_idx = 0
        best_effective_score = None
        for idx, item in enumerate(remaining):
            penalty = 0.0
            item_tokens = token_sets[id(item["candidate"])]
            for sel in selected:
                sel_tokens = token_sets[id(sel["candidate"])]
                if _jaccard(item_tokens, sel_tokens) > DIVERSITY_PENALTY_THRESHOLD:
                    penalty = max(penalty, DIVERSITY_PENALTY)
            effective = item["score"] - penalty
            if best_effective_score is None or effective > best_effective_score:
                best_effective_score = effective
                best_idx = idx
        chosen = remaining.pop(best_idx)
        chosen["final_score"] = best_effective_score
        selected.append(chosen)

    return [
        {
            "chunk": item["candidate"].chunk,
            "score": item["final_score"],
            "raw_score": item["raw_score"],
            "graph_linked": item["candidate"].graph_linked,
        }
        for item in selected
    ]
