"""
Seeds a realistic sample corpus across all ten RAG_SYSTEM.md §1 document
classes into `knowledge_documents`, via the real `POST /knowledge-base/documents`
API (not a direct DB insert) so the seed exercises the same write path a real
Safety Officer would use. Content is original, demo-plant-specific writing
(reusing "Aegis Demo Refinery" / "Valve V-12" from this repo's established
demo narrative) -- not copied real statutory text -- but each document is
structured with the exact boundary markers (Section N:, Step N:, ## Section,
Finding N:, etc.) app/rag/chunking.py's per-class splitters expect, so
running this seed is also a real test that chunking behaves correctly on
realistic input.

Usage: run against a live rag-service + Postgres:
    python scripts/seed_corpus.py
"""

from __future__ import annotations

import asyncio
import time

import asyncpg
import httpx
from jose import jwt

RAG_SERVICE_URL = "http://localhost:8008"
POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
JWT_SECRET = "changeme_generate_a_real_secret_before_any_shared_deployment"
JWT_ALGORITHM = "HS256"


async def mint_safety_officer_token() -> str:
    """Unlike notification-service's alert/risk-score creation (which never
    look up the caller's user_id beyond the role check), knowledge_base's
    create_document sets `created_by` to a real FK against `users.id` -- so,
    unlike computer-vision's downstream integration, this mint needs a real
    seeded user row, not an arbitrary sentinel id."""
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        row = await conn.fetchrow(
            "SELECT u.id, u.default_role_id FROM users u JOIN roles r ON r.id = u.default_role_id "
            "WHERE r.name = 'safety_officer' LIMIT 1"
        )
    finally:
        await conn.close()
    if row is None:
        raise RuntimeError("No seeded safety_officer user found -- has the demo DB been seeded?")
    payload = {"sub": str(row["id"]), "role_id": row["default_role_id"], "type": "access", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


DOCUMENTS = [
    {
        "title": "Factories Act, 1948 — Selected Provisions",
        "document_class": "factory_act",
        "authority": "statutory",
        "version": "1948 (as amended)",
        "effective_date": "1948-04-01",
        "content": (
            "Section 87: Dangerous operations\n"
            "(1) If the Central Government is satisfied that any manufacturing process or operation carried on "
            "in a factory involves risk of bodily injury, poisoning, or disease, it may make rules applicable to "
            "any factory or class of factories in which the process is carried on, imposing special measures.\n\n"
            "Section 87(2): Special measures for hazardous processes\n"
            "The rules made under sub-section (1) may provide for the periodic medical examination of persons "
            "employed in or about a hazardous process, the maintenance of exposure records, and restrictions on "
            "the number of hours a worker may be employed in a hazardous process during any one day.\n\n"
            "Section 88: Notice of certain accidents\n"
            "Where in any factory an accident occurs which causes death or which causes any bodily injury as a "
            "result of which the person injured is prevented from working for a period of 48 hours or more, the "
            "manager of the factory shall send notice to the appropriate authority within the prescribed time."
        ),
    },
    {
        "title": "DGMS Circular No. 7/2019 — Gas Detection Systems in Confined Process Areas",
        "document_class": "dgms",
        "authority": "regulatory",
        "version": "1",
        "effective_date": "2019-03-12",
        "content": (
            "Clause 1: Applicability\n"
            "This circular applies to all confined and semi-confined process areas where flammable or toxic "
            "gases may accumulate, including but not limited to tank farms, compressor houses, and reactor bays.\n\n"
            "Clause 2: Minimum detection threshold\n"
            "Fixed gas detectors shall be calibrated to raise a warning alarm at 10 percent LEL and a critical "
            "alarm at 20 percent LEL. No detector shall be commissioned with a warning threshold above 15 percent LEL.\n\n"
            "Clause 3: Inspection interval\n"
            "Every fixed gas detector shall be functionally tested at intervals not exceeding 90 days, and the "
            "test record retained for a minimum of three years."
        ),
    },
    {
        "title": "OISD-STD-118 — Fire Protection Facilities for Petroleum Refineries",
        "document_class": "oisd",
        "authority": "regulatory",
        "version": "3",
        "effective_date": "2021-06-01",
        "content": (
            "Clause 4.2: Sprinkler system coverage\n"
            "All process areas classified as Hazard Class H1 or above shall be provided with automatic sprinkler "
            "or deluge protection sized for the area's fire load, per the facility's fire hazard analysis.\n\n"
            "Clause 4.3: Inspection interval\n"
            "Fixed fire suppression systems shall be inspected at intervals not exceeding 180 days, and a full "
            "functional discharge test performed not less than once every 3 years.\n\n"
            "Clause 4.4: Valve accessibility\n"
            "Isolation valves for fire water and foam systems shall remain accessible and clearly tagged at all "
            "times, and shall never be located behind process equipment requiring confined-space entry to reach."
        ),
    },
    {
        "title": "SOP-1042 — Isolation and Lockout of Feed Valves Prior to Maintenance",
        "document_class": "safety_sop",
        "authority": "internal",
        "version": "3",
        "effective_date": "2025-11-01",
        "content": (
            "Step 1: Notify the control room and confirm the equipment has been placed in maintenance mode "
            "before any isolation work begins.\n\n"
            "Step 2: Close the upstream and downstream isolation valves for the equipment under maintenance, "
            "confirming closure both locally and on the control room HMI.\n\n"
            "Step 3: Apply a lockout tag to each isolation valve identified in Step 2, and verify zero energy "
            "state before proceeding.\n\n"
            "Step 4: Obtain a hot work or cold work permit, as applicable, before any tool contacts the "
            "isolated equipment.\n\n"
            "Step 5: On completion, remove lockout tags only after a second qualified worker independently "
            "confirms the work is finished and the area is clear."
        ),
    },
    {
        "title": "Reactor Feed Isolation Valve (V-12) — Manufacturer Manual",
        "document_class": "equipment_manual",
        "authority": "vendor",
        "version": "Rev. 2",
        "effective_date": "2023-01-15",
        "equipment_type_scope": "Valve",
        "content": (
            "## Section 1: Overview\n"
            "The V-12 series is a gate-type isolation valve rated for process fluid service up to 25 bar and "
            "150 degrees Celsius, intended for feed-line isolation duty.\n\n"
            "## Section 2: Torque Specification\n"
            "| Bolt Size | Torque (Nm) | Sequence |\n"
            "| M12 | 45 | Cross-pattern |\n"
            "| M16 | 95 | Cross-pattern |\n"
            "| M20 | 165 | Cross-pattern |\n\n"
            "## Section 3: Inspection Interval\n"
            "Routine inspection of the packing gland and seat is required at intervals not exceeding 180 days "
            "under normal service conditions."
        ),
    },
    {
        "title": "Conveyor Motor Maintenance Manual — Model CM-400 Series",
        "document_class": "maintenance_manual",
        "authority": "vendor",
        "version": "Rev. 1",
        "effective_date": "2022-08-01",
        "equipment_type_scope": "Compressor",
        "content": (
            "## Section 1: Lubrication Schedule\n"
            "Bearing lubrication shall be performed every 90 days under normal duty cycle, or every 45 days "
            "under continuous heavy-load operation.\n\n"
            "## Section 2: Vibration Limits\n"
            "Sustained vibration readings above 7.1 mm/s at the drive-end bearing indicate a developing fault "
            "and warrant immediate inspection before continued operation."
        ),
    },
    {
        "title": "Incident INC-2026-000482 — Tank Farm Gas Alarm Escalation",
        "document_class": "incident_report",
        "authority": "internal",
        "version": "1",
        "effective_date": "2026-06-14",
        "hazard_class_scope": "H1",
        "content": (
            "Summary:\n"
            "A confirmed gas leak was detected in the Tank Farm zone following a flange gasket failure on the "
            "outlet line from Storage Tank T-301.\n\n"
            "Timeline:\n"
            "14:02 - Fixed gas detector GS-14 crossed the 10 percent LEL warning threshold. "
            "14:06 - Reading crossed 20 percent LEL, triggering automatic zone evacuation. "
            "14:11 - Emergency response team confirmed the source as a flange gasket failure.\n\n"
            "Root Cause:\n"
            "Post-incident inspection found the flange gasket had exceeded its service life by approximately "
            "14 months; the applicable replacement interval had not been tracked in the maintenance schedule.\n\n"
            "Corrective Action:\n"
            "Gasket replacement intervals for all flanged connections in Hazard Class H1 zones were added to "
            "the preventive maintenance schedule with a 24-month replacement cycle."
        ),
    },
    {
        "title": "Near Miss NM-2026-000117 — Unsecured Ladder Near Compressor House",
        "document_class": "near_miss",
        "authority": "internal",
        "version": "1",
        "effective_date": "2026-05-02",
        "content": (
            "Summary:\n"
            "A maintenance worker found an unsecured extension ladder leaning against the compressor house "
            "exterior wall, unattended, with no barricade or spotter present.\n\n"
            "Root Cause:\n"
            "The ladder had been left in place after a completed inspection the previous shift, in violation of "
            "the tool and equipment stowage requirement in SOP-1042."
        ),
    },
    {
        "title": "Audit AUD-2026-014 — Annual Fire Protection Systems Compliance Audit",
        "document_class": "audit_report",
        "authority": "internal",
        "version": "1",
        "effective_date": "2026-03-20",
        "content": (
            "Finding 1: Sprinkler discharge test overdue\n"
            "The Boiler Room deluge system's full functional discharge test was last performed 41 months ago, "
            "exceeding OISD-STD-118 Clause 4.3's 3-year interval requirement.\n\n"
            "Finding 2: Fire water isolation valve accessibility\n"
            "One fire water isolation valve in the Tank Farm zone was found partially obstructed by a "
            "temporarily stored pallet, in apparent tension with Clause 4.4's accessibility requirement.\n\n"
            "Finding 3: Gas detector calibration records complete\n"
            "All fixed gas detector calibration records reviewed were current and within the 90-day interval "
            "required by DGMS Circular No. 7/2019."
        ),
    },
    {
        "title": "Inspection INSP-2026-000891 — Storage Tank T-301 Routine Inspection",
        "document_class": "inspection_report",
        "authority": "internal",
        "version": "1",
        "effective_date": "2026-06-01",
        "content": (
            "Finding 1: External shell condition satisfactory\n"
            "No visible corrosion or coating failure observed on the external shell during walk-down "
            "inspection.\n\n"
            "Finding 2: Outlet flange gasket approaching end of service life\n"
            "The outlet line flange gasket showed early signs of weeping and was flagged for replacement "
            "within the next maintenance window."
        ),
    },
]


async def seed() -> None:
    token = await mint_safety_officer_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        created = []
        for doc in DOCUMENTS:
            response = await client.post(f"{RAG_SERVICE_URL}/knowledge-base/documents", json=doc, headers=headers)
            response.raise_for_status()
            created.append(response.json()["id"])
        print(f"Seeded {len(created)} documents: {created}")

        reindex_response = await client.post(f"{RAG_SERVICE_URL}/rag/reindex", headers=headers)
        reindex_response.raise_for_status()
        print("Reindex result:", reindex_response.json())


if __name__ == "__main__":
    asyncio.run(seed())
