"""
The chunk metadata envelope — RAG_SYSTEM.md §6. Every chunk, regardless of
document class, carries this schema; it is what makes temporal scoping
(§5.4), access filtering (§5.5), graph-boosting (§5.2/§7.2), and citation
rendering (§8.1) possible without per-document-class special-casing at
query time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

REGULATION_CLASSES = {"factory_act", "dgms", "oisd"}

# §2.4: "some audit findings and incident root-cause narratives may be classified
# for Safety Officer/Plant Manager eyes only." A real, enforced, class-based access
# policy (indexing.py/retrieval.py apply it) -- see indexing.py's docstring for why
# this is computed from document_class rather than a per-document override column.
RESTRICTED_DOCUMENT_CLASSES = {"audit_report", "incident_report"}
ALLOWED_ROLES_FOR_RESTRICTED = {"system_admin", "plant_admin", "safety_officer"}

# RAG_SYSTEM.md §1's table, condensed to what this pipeline actually needs:
# authority model + the KNOWLEDGE_GRAPH.md §2.4 Document subtype each class maps to.
DOCUMENT_CLASS_INFO: dict[str, dict] = {
    "safety_sop": {"authority": "internal", "graph_label": "Procedure"},
    "equipment_manual": {"authority": "vendor", "graph_label": "Manual"},
    "factory_act": {"authority": "statutory", "graph_label": None},
    "dgms": {"authority": "regulatory", "graph_label": None},
    "oisd": {"authority": "regulatory", "graph_label": None},
    "maintenance_manual": {"authority": "vendor", "graph_label": "Manual"},
    "incident_report": {"authority": "internal", "graph_label": "InspectionReport"},
    "near_miss": {"authority": "internal", "graph_label": "InspectionReport"},
    "audit_report": {"authority": "internal", "graph_label": "InspectionReport"},
    "inspection_report": {"authority": "internal", "graph_label": "InspectionReport"},
}


@dataclass(frozen=True)
class ChunkMetadata:
    chunk_id: str
    document_id: int
    document_class: str
    authority: str
    version: str | None
    effective_date: date | None
    superseded_at: datetime | None
    section_reference: str | None
    equipment_type_scope: str | None
    hazard_class_scope: str | None
    jurisdiction: str | None
    graph_node_id: int | None
    access_classification: str
    ocr_confidence: float | None
    citation_template: str  # rendered citation string, see citation.py

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_class": self.document_class,
            "authority": self.authority,
            "version": self.version,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "superseded_at": self.superseded_at.isoformat() if self.superseded_at else None,
            "section_reference": self.section_reference,
            "equipment_type_scope": self.equipment_type_scope,
            "hazard_class_scope": self.hazard_class_scope,
            "jurisdiction": self.jurisdiction,
            "graph_node_id": self.graph_node_id,
            "access_classification": self.access_classification,
            "ocr_confidence": self.ocr_confidence,
            "citation": self.citation_template,
        }


@dataclass
class Chunk:
    """One retrievable unit. `embedding` is populated by embeddings.py at
    index time and never serialized back to API callers (§4 -- an embedding
    vector is an internal implementation detail, not part of the contract)."""

    text: str
    metadata: ChunkMetadata
    embedding: list[float] | None = field(default=None, repr=False)
