"""
Builds the in-memory chunk index (store.py's `ChunkIndex`) from every row
currently in `knowledge_documents` -- both currently-effective and
superseded, per store.py's docstring.

Two fields RAG_SYSTEM.md §6 specifies aren't yet real columns on
`knowledge_documents` (that table predates this pipeline, built as a bare
CRUD scaffold in an earlier pass): `access_classification` and
`jurisdiction`. Rather than a speculative Alembic migration against the
shared libs/db chain every other service also depends on, both are computed
here as a deterministic, class-based policy -- a real, enforced access-control
behavior (§5.5), just keyed off `document_class` instead of a per-document
override column. `graph_node_id` needs no such workaround: it is simply the
document's own id, since KNOWLEDGE_GRAPH.md §1.2's identity rule and this
service's sync already guarantee `Document.id == knowledge_documents.id`.
"""

from __future__ import annotations

import asyncpg
import structlog

from app.rag.chunking import chunk_document
from app.rag.citation import render_citation
from app.rag.embeddings import EMBEDDING_MODEL_VERSION, embedding_model
from app.rag.schema import REGULATION_CLASSES, RESTRICTED_DOCUMENT_CLASSES, Chunk, ChunkMetadata
from app.rag.store import ChunkIndex

logger = structlog.get_logger(__name__)


def access_classification_for(document_class: str) -> str:
    return "restricted" if document_class in RESTRICTED_DOCUMENT_CLASSES else "standard"


def jurisdiction_for(document_class: str) -> str | None:
    return "India" if document_class in REGULATION_CLASSES else None


async def build_chunks_from_postgres(dsn: str) -> list[Chunk]:
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT id, title, document_class, authority, content, section_reference, "
            "version, effective_date, superseded_at, equipment_type_scope, hazard_class_scope "
            "FROM knowledge_documents"
        )
    finally:
        await conn.close()

    chunks: list[Chunk] = []
    for row in rows:
        pieces = chunk_document(row["content"], row["document_class"])
        for i, (chunk_text, section_ref) in enumerate(pieces):
            resolved_section_ref = section_ref or row["section_reference"]
            citation = render_citation(
                document_class=row["document_class"], title=row["title"], version=row["version"],
                section_reference=resolved_section_ref, effective_date=row["effective_date"],
            )
            metadata = ChunkMetadata(
                chunk_id=f"c_{row['id']}_{i}",
                document_id=row["id"],
                document_class=row["document_class"],
                authority=row["authority"],
                version=row["version"],
                effective_date=row["effective_date"],
                superseded_at=row["superseded_at"],
                section_reference=resolved_section_ref,
                equipment_type_scope=row["equipment_type_scope"],
                hazard_class_scope=row["hazard_class_scope"],
                jurisdiction=jurisdiction_for(row["document_class"]),
                graph_node_id=row["id"],
                access_classification=access_classification_for(row["document_class"]),
                ocr_confidence=None,
                citation_template=citation,
            )
            chunks.append(Chunk(text=chunk_text, metadata=metadata))

    if chunks:
        embeddings = embedding_model.embed([c.text for c in chunks])
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

    return chunks


async def rebuild_index(index: ChunkIndex, dsn: str) -> dict:
    chunks = await build_chunks_from_postgres(dsn)
    index.rebuild(chunks)
    logger.info("rag_index_rebuilt", chunk_count=len(chunks), embedding_model=EMBEDDING_MODEL_VERSION)
    return {"chunks_indexed": len(chunks), "documents": len({c.metadata.document_id for c in chunks})}
