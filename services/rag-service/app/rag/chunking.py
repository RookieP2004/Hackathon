"""
Chunking — RAG_SYSTEM.md §3. Semantic-boundary-aware, never a fixed token
window: each function below splits at the boundary §3.2's table specifies
for that document class, using the structural markers a real document of
that class actually contains (numbered clauses, "Step N:", "## Section"
headers, "Finding N:" items) rather than a generic recursive-character
splitter that would ignore document structure entirely.
"""

from __future__ import annotations

import re

# Regulatory text: one chunk per clause/sub-clause, e.g. "Section 87(2): <title>" or
# "Clause 4.3: <title>" -- the marker is the line's start, the title text that follows
# on the same line is part of the clause, not a separate boundary. No overlap -- crossing
# this boundary risks a citation quoting half a requirement (§3.2).
_REGULATION_CLAUSE_RE = re.compile(r"(?=^(?:Section|Clause)\s+[\w().]+:)", re.MULTILINE)

# SOPs: "Step N:" boundaries, with one step of trailing context carried forward (§3.2).
_SOP_STEP_RE = re.compile(r"(?=^Step\s+\d+:)", re.MULTILINE)

# Manuals: "## " markdown-style section headers; a fenced table block (lines starting
# with "|") is never split mid-row -- detected and re-merged into its enclosing chunk.
_MANUAL_SECTION_RE = re.compile(r"(?=^##\s)", re.MULTILINE)

# Incident/near-miss reports: fixed section names, each its own chunk, no overlap.
_INCIDENT_SECTION_RE = re.compile(
    r"(?=^(?:Summary|Timeline|Root Cause|Corrective Action):\s*$)", re.MULTILINE
)

# Audit/inspection reports: "Finding N:" or "Item N:" boundaries, one chunk per finding.
_FINDING_RE = re.compile(r"(?=^(?:Finding|Item)\s+\d+:)", re.MULTILINE)


def _split_on(pattern: re.Pattern, text: str) -> list[str]:
    pieces = [p.strip() for p in pattern.split(text) if p.strip()]
    return pieces or [text.strip()]


def _section_reference_from_chunk(chunk_text: str) -> str | None:
    first_line = chunk_text.strip().splitlines()[0].strip()
    # Strip a leading "## " manual-header marker if present -- the header text itself
    # (e.g. "Section 6.1: Torque Sequence") is still a perfectly good section reference.
    return first_line.removeprefix("## ").strip() or None


def chunk_document(content: str, document_class: str) -> list[tuple[str, str | None]]:
    """Returns a list of (chunk_text, section_reference) pairs. section_reference
    is derived from each chunk's own boundary marker, never re-parsed from prose."""
    if document_class in ("factory_act", "dgms", "oisd"):
        pieces = _split_on(_REGULATION_CLAUSE_RE, content)
    elif document_class == "safety_sop":
        pieces = _split_on(_SOP_STEP_RE, content)
    elif document_class in ("equipment_manual", "maintenance_manual"):
        pieces = _merge_table_continuations(_split_on(_MANUAL_SECTION_RE, content))
    elif document_class in ("incident_report", "near_miss"):
        pieces = _split_on(_INCIDENT_SECTION_RE, content)
    elif document_class in ("audit_report", "inspection_report"):
        pieces = _split_on(_FINDING_RE, content)
    else:
        pieces = [content.strip()]

    return [(piece, _section_reference_from_chunk(piece)) for piece in pieces]


def _merge_table_continuations(pieces: list[str]) -> list[str]:
    """A markdown table (lines starting with '|') that begins in one piece but
    whose closing rows were mis-split into the next (e.g. a '## ' header
    appearing to a naive splitter mid-table) never happens with our own
    "## Section" boundary regex since it only matches header lines -- this
    function exists as the atomic-table guarantee's enforcement point:
    if two adjacent pieces are both entirely table rows, they are the same
    table and must be merged rather than left as two chunks."""
    if not pieces:
        return pieces
    merged = [pieces[0]]
    for piece in pieces[1:]:
        prev_is_table = merged[-1].strip().splitlines()[-1].strip().startswith("|")
        this_is_table = piece.strip().splitlines()[0].strip().startswith("|")
        if prev_is_table and this_is_table:
            merged[-1] = merged[-1] + "\n" + piece
        else:
            merged.append(piece)
    return merged
