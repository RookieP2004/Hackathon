"""
Intent classification for the AI Copilot. No LLM is available in this
environment, so recognizing what the user is asking for is done the honest
way: semantic similarity (the same sentence-transformers embedding model
rag-service already loads for retrieval) between the user's free-text
question and a small bank of canonical example phrasings per intent -- not
brittle keyword/regex matching, and not a fabricated call to a model that
isn't actually deployed here.
"""

from __future__ import annotations

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

INTENT_EXAMPLES: dict[str, list[str]] = {
    "current_state": [
        "what is happening", "what's going on right now", "give me the current status",
        "what's the situation at the plant", "any active incidents or alerts",
        "show me what's happening now", "current plant status", "summarize the current situation",
    ],
    "why_risk_increasing": [
        "why is risk increasing", "why did the risk score go up", "explain the risk increase",
        "what is driving this risk", "why is this equipment risky", "what's causing the high risk score",
        "explain why the fire risk is high", "why is the explosion risk elevated",
    ],
    "machine_history": [
        "show machine history", "what is the history of this equipment", "show me equipment history",
        "past maintenance and incidents for this machine", "give me the history of this machine",
        "show sensor and maintenance history", "what has happened with this equipment before",
    ],
    "predict_failures": [
        "predict failures", "when will this machine fail", "estimate time to failure",
        "predict equipment breakdowns", "what is the time to failure", "forecast machine failure",
        "how long until this fails",
    ],
    "permit_violations": [
        "show permit violations", "which permits have expired", "list expired permits still active",
        "show permit compliance issues", "any permit violations right now", "are there any expired work permits",
    ],
    "generate_inspection_report": [
        "generate an inspection report", "create an inspection report for this equipment",
        "produce a report for this machine", "generate a report", "write up an inspection report",
    ],
    "similar_incidents": [
        "find similar incidents", "show incidents like this one", "have similar incidents happened before",
        "find historical incidents similar to this equipment", "show comparable past incidents",
    ],
    "explain_regulation": [
        "explain this regulation", "what does this standard require", "explain the relevant procedure",
        "what is the governing regulation", "explain the safety standard", "what does the safety code say",
        "which regulation applies here",
    ],
}

CONFIDENCE_THRESHOLD = 0.35


class IntentClassifier:
    def __init__(self) -> None:
        self._model = None
        self._intent_names: list[str] = []
        self._example_intent_index: list[int] = []
        self._example_embeddings: np.ndarray | None = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        logger.info("copilot_intent_model_loading", model=EMBEDDING_MODEL_NAME)
        self._model = SentenceTransformer(EMBEDDING_MODEL_NAME)

        example_texts = []
        self._intent_names = list(INTENT_EXAMPLES.keys())
        for idx, intent in enumerate(self._intent_names):
            for example in INTENT_EXAMPLES[intent]:
                example_texts.append(example)
                self._example_intent_index.append(idx)
        self._example_embeddings = np.array(self._model.encode(example_texts, normalize_embeddings=True, show_progress_bar=False))
        logger.info("copilot_intent_model_loaded", num_examples=len(example_texts))

    def classify(self, query: str) -> tuple[str, float]:
        self._ensure_loaded()
        query_embedding = np.array(self._model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0])
        similarities = self._example_embeddings @ query_embedding
        best_idx = int(similarities.argmax())
        best_score = float(similarities[best_idx])
        best_intent = self._intent_names[self._example_intent_index[best_idx]]
        if best_score < CONFIDENCE_THRESHOLD:
            return "unknown", best_score
        return best_intent, best_score


classifier = IntentClassifier()
