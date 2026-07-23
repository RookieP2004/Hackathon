from app.rag.chunking import chunk_document


def test_factory_act_splits_on_section_boundaries_with_no_overlap():
    content = (
        "Section 87: Dangerous operations\nSome text about hazardous processes.\n\n"
        "Section 88: Notice of certain accidents\nSome text about accident notice requirements."
    )
    chunks = chunk_document(content, "factory_act")
    assert len(chunks) == 2
    assert chunks[0][1] == "Section 87: Dangerous operations"
    assert chunks[1][1] == "Section 88: Notice of certain accidents"
    assert "Dangerous operations" not in chunks[1][0]  # no cross-clause bleed


def test_oisd_clause_numbers_are_preserved_as_section_reference():
    content = "Clause 4.2: Sprinkler coverage\nCoverage text.\n\nClause 4.3: Inspection interval\nInterval text."
    chunks = chunk_document(content, "oisd")
    assert chunks[0][1] == "Clause 4.2: Sprinkler coverage"
    assert chunks[1][1] == "Clause 4.3: Inspection interval"


def test_sop_splits_on_step_boundaries():
    content = "Step 1: Do the first thing.\n\nStep 2: Do the second thing.\n\nStep 3: Do the third thing."
    chunks = chunk_document(content, "safety_sop")
    assert len(chunks) == 3
    assert all(c[1].startswith("Step") for c in chunks)


def test_manual_splits_on_markdown_sections():
    content = "## Section 1: Overview\nOverview text.\n\n## Section 2: Torque Spec\nSpec text."
    chunks = chunk_document(content, "equipment_manual")
    assert len(chunks) == 2
    assert chunks[0][1] == "Section 1: Overview"


def test_manual_table_stays_atomic_within_its_section():
    content = (
        "## Section 2: Torque Specification\n"
        "| Bolt Size | Torque (Nm) |\n"
        "| M12 | 45 |\n"
        "| M16 | 95 |\n"
    )
    chunks = chunk_document(content, "equipment_manual")
    assert len(chunks) == 1
    assert "M12" in chunks[0][0] and "M16" in chunks[0][0]


def test_incident_report_splits_on_fixed_sections():
    content = "Summary:\nWhat happened.\n\nTimeline:\nWhen it happened.\n\nRoot Cause:\nWhy it happened.\n\nCorrective Action:\nWhat was done."
    chunks = chunk_document(content, "incident_report")
    assert len(chunks) == 4
    assert [c[1] for c in chunks] == ["Summary:", "Timeline:", "Root Cause:", "Corrective Action:"]


def test_audit_report_splits_on_findings():
    content = "Finding 1: First issue.\n\nFinding 2: Second issue.\n\nFinding 3: Third issue."
    chunks = chunk_document(content, "audit_report")
    assert len(chunks) == 3


def test_unknown_class_falls_back_to_single_chunk():
    chunks = chunk_document("Some arbitrary text.", "unknown_class")
    assert len(chunks) == 1
