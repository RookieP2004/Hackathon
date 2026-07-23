"""
The scripted story, in order. Each step's wait_after_seconds is the base
pacing at 1x speed -- the player divides it by the active speed multiplier
for fast-forward.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from app.demo import actions
from app.demo.context import DemoContext


@dataclass
class DemoStep:
    id: str
    title: str
    narration: str
    action: Callable[[DemoContext], Awaitable[dict]]
    wait_after_seconds: float


def build_script() -> list[DemoStep]:
    return [
        DemoStep(
            "normal", "Normal Operations",
            "V-12 (Reactor Feed Isolation Valve, Zone 3) is operating normally. A Hot Work permit is issued and active for today's shift.",
            actions.setup_baseline, 8.0,
        ),
        DemoStep(
            "gas_rises", "Gas Concentration and Temperature Rising",
            "GS-14 begins reading a gradual rise in gas concentration on V-12, and TE-201 shows an accompanying temperature climb.",
            actions.inject_gas_rise, 25.0,
        ),
        DemoStep(
            "vibration_increases", "Vibration Increasing",
            "Meanwhile, VI-202 on RV-9 shows a climbing vibration trend -- a second precursor developing in parallel elsewhere in the plant.",
            actions.inject_vibration_rise, 25.0,
        ),
        DemoStep(
            "maintenance_begins", "Maintenance Dispatched",
            "Maintenance engineer Tasha Reyes is dispatched to investigate -- a corrective work order is opened and marked in progress.",
            actions.begin_maintenance, 6.0,
        ),
        DemoStep(
            "worker_enters", "Worker Enters the Zone",
            "Operator Priya Sharma enters Zone 3 (Reactor Feed Line) for her shift.",
            actions.worker_enters_zone, 6.0,
        ),
        DemoStep(
            "permit_expires", "Permit Expires",
            "The active Hot Work permit on V-12 has just passed its expiry -- work is continuing without a currently valid permit.",
            actions.expire_permit, 6.0,
        ),
        DemoStep(
            "camera_detects_fire", "Camera Detects Fire",
            "The camera covering the zone where V-12 sits detects a fire signature.",
            actions.camera_detects_fire, 10.0,
        ),
        DemoStep(
            "risk_increasing", "Risk Score Climbing",
            "The Risk Fusion Engine's continuous live assessment of V-12 now reflects the elevated gas reading and the camera detection.",
            actions.observe_current_risk, 8.0,
        ),
        DemoStep(
            "ai_explains", "AI Explains Why",
            "Ask the Copilot why -- a real, cited explanation grounded in the Risk Fusion Engine's own evidence, not a canned line.",
            actions.ask_ai_why, 8.0,
        ),
        DemoStep(
            "emergency_response", "Automatic Emergency Response",
            "Watching for the moment the live agent fleet's Prediction Agent and Emergency Agent respond automatically to critical risk...",
            actions.wait_for_emergency_response, 2.0,
        ),
        DemoStep(
            "reports_generated", "Reports Generated",
            "Incident and regulatory PDF reports were generated automatically as part of the emergency response.",
            actions.summarize_reports, 4.0,
        ),
    ]
