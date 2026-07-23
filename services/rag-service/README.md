# rag-service

Embedding, retrieval, and grounded evidence assembly, per RAG_SYSTEM.md and AGENT_ARCHITECTURE.md section 6.

Ten document classes (Safety SOPs, Equipment/Maintenance Manuals, Factory Act,
DGMS, OISD, Incident Reports, Near Misses, Audit Reports, Inspection Reports)
live in `knowledge_documents` (the `knowledge-base` module). `app/rag/`
implements the retrieval pipeline on top of it:

- **Chunking** (`chunking.py`) — semantic-boundary-aware, per document-class
  strategy from RAG_SYSTEM.md §3.2 (clause-bounded for regulatory text,
  step-bounded for SOPs, section/table-atomic for manuals, fixed-section for
  incidents, finding-bounded for audits).
- **Embeddings** (`embeddings.py`) — real `sentence-transformers` model, one
  domain-wide embedding space per §4.1.
- **OCR** (`ocr.py`) — real local `easyocr` engine for scanned-document
  ingestion, per §2.2, with a genuine `ocr_confidence` score.
- **Hybrid search** (`retrieval.py`) — BM25 + vector cosine similarity +
  knowledge-graph-scoped traversal (a real call to the `knowledge-graph`
  service), fused via Reciprocal Rank Fusion (§5).
- **Re-ranking** (`reranking.py`) — a real cross-encoder re-scores the fused
  candidates, plus graph-aware boost, diversity-aware selection, and a
  recency/supersession penalty (§7).
- **Citation** (`citation.py`) — class-specific rendered citation strings (§8.1).
- **Hallucination prevention** (`hallucination.py`) — low-confidence refusal,
  numeric cross-source conflict detection, and a real local NLI model for
  claim-vs-source entailment verification (§9). Generation itself (writing
  the answer text) is the future AI Copilot's job, not this service's — see
  `pipeline.py`'s docstring for why (no LLM API key is configured in this
  environment).
- **Feedback** (`store.py`) — thumbs up/down and corpus-gap detection (§10).

The chunk+embedding index is an in-memory, rebuildable materialized view over
`knowledge_documents` (`POST /rag/reindex`), the same "derived, rebuildable
projection" pattern the `knowledge-graph` service's Neo4j sync uses.

Seed a demo corpus: `python scripts/seed_corpus.py` (requires the service and
Postgres running).

**Local dev:** `cd services/rag-service && poetry install && poetry run uvicorn app.main:app --reload`
