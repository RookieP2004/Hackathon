"""
Embeddings — RAG_SYSTEM.md §4. §4.1 specifies a single domain-adapted model,
continuously fine-tuned on the corpus. Fine-tuning infrastructure (continued
pretraining, contrastive fine-tuning from feedback, held-out-set evaluation,
human-gated promotion per §4.3/§10.3) is a genuinely separate, larger
undertaking than fits in this pass -- what's implemented here is the honest
subset: one real, pretrained sentence-embedding model, used consistently for
every document class so cross-class retrieval works in one pass exactly as
§4.1 requires, with the embedding-versioning discipline (§4.3) enforced via
a `model_version` tag on every stored vector so a future re-embedding pass
has a real cutover point to key off, not an implicit assumption.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

EMBEDDING_MODEL_VERSION = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingModel:
    def __init__(self, model_name: str = EMBEDDING_MODEL_VERSION) -> None:
        self._model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("embedding_model_loading", model=self._model_name)
            self._model = SentenceTransformer(self._model_name)
            logger.info("embedding_model_loaded", model=self._model_name)
        return self._model

    def warm_up(self) -> None:
        self._get_model()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._get_model()
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


embedding_model = EmbeddingModel()
