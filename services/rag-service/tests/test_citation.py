from datetime import date

from app.rag.citation import render_citation


def test_factory_act_citation():
    result = render_citation(
        document_class="factory_act", title="Factories Act, 1948", version=None,
        section_reference="Section 87(2)", effective_date=None,
    )
    assert result == "Factories Act, 1948, Section 87(2)"


def test_dgms_citation_includes_date():
    result = render_citation(
        document_class="dgms", title="Circular No. 4/2019", version=None,
        section_reference=None, effective_date=date(2019, 3, 12),
    )
    assert result == "DGMS Circular No. 4/2019, dated 12 Mar 2019"


def test_oisd_citation_includes_clause_and_revision():
    result = render_citation(
        document_class="oisd", title="OISD-STD-118", version="3",
        section_reference="Clause 4.3", effective_date=date(2021, 6, 1),
    )
    assert result == "OISD-STD-118, Clause 4.3 (Rev. 3, 2021)"


def test_sop_citation():
    result = render_citation(
        document_class="safety_sop", title="SOP-1042", version="3",
        section_reference="Section 4.2", effective_date=None,
    )
    assert result == "SOP-1042, v3, Section 4.2"


def test_incident_report_citation():
    result = render_citation(
        document_class="incident_report", title="INC-2026-000482", version=None,
        section_reference="Root Cause section", effective_date=None,
    )
    assert result == "Incident INC-2026-000482, Root Cause section"


def test_audit_report_citation():
    result = render_citation(
        document_class="audit_report", title="AUD-2026-014", version=None,
        section_reference="Finding 12", effective_date=None,
    )
    assert result == "AUD-2026-014, Finding 12"
