"""
Citation generation — RAG_SYSTEM.md §8.1: "A single [source 1]-style generic
citation is inadequate for a corpus this heterogeneous." Each document class
renders in the convention a Safety Officer or auditor would actually
recognize and could independently verify, per §8.1's table.
"""

from __future__ import annotations

from datetime import date


def render_citation(
    *, document_class: str, title: str, version: str | None, section_reference: str | None,
    effective_date: date | None,
) -> str:
    if document_class == "factory_act":
        return f"Factories Act, 1948, {section_reference}" if section_reference else "Factories Act, 1948"

    if document_class == "dgms":
        date_str = f", dated {effective_date.strftime('%d %b %Y')}" if effective_date else ""
        return f"DGMS {title}{date_str}"

    if document_class == "oisd":
        rev = f" (Rev. {version}, {effective_date.year})" if version and effective_date else ""
        clause = f", {section_reference}" if section_reference else ""
        return f"{title}{clause}{rev}"

    if document_class == "safety_sop":
        v = f", v{version}" if version else ""
        section = f", {section_reference}" if section_reference else ""
        return f"{title}{v}{section}"

    if document_class in ("equipment_manual", "maintenance_manual"):
        section = f", {section_reference}" if section_reference else ""
        return f"{title}{section}"

    if document_class == "incident_report":
        section = f", {section_reference}" if section_reference else ""
        return f"Incident {title}{section}"

    if document_class == "near_miss":
        section = f", {section_reference}" if section_reference else ""
        return f"Near Miss {title}{section}"

    if document_class in ("audit_report", "inspection_report"):
        section = f", {section_reference}" if section_reference else ""
        return f"{title}{section}"

    return title
