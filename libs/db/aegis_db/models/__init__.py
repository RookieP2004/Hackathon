"""
Import every model module here so Base.metadata is fully populated the moment
`aegis_db.models` is imported once, anywhere — this is what Alembic's env.py
relies on for autogenerate, and what any service needs to do exactly once at
startup before issuing any query.
"""

from aegis_db.models.lookups import Role, EquipmentType, SensorType, PermitType, MaintenanceType, Employer
from aegis_db.models.organization import Plant, Building, Zone
from aegis_db.models.assets import Equipment, Machine, Sensor
from aegis_db.models.identity import User, Worker, UserRoleScope, Shift, ShiftAssignment
from aegis_db.models.auth import RefreshToken, PasswordResetToken
from aegis_db.models.permits import Permit
from aegis_db.models.maintenance import MaintenanceRecord
from aegis_db.models.incidents import Incident, IncidentTimelineEvent
from aegis_db.models.risk import RiskScore, Prediction
from aegis_db.models.alerts import Alert
from aegis_db.models.emergency import Playbook, PlaybookStep, EmergencyEvent, EmergencyEventStep
from aegis_db.models.vision import Camera, CameraEvent, PPEViolation
from aegis_db.models.audit import AuditLog
from aegis_db.models.notifications import Notification
from aegis_db.models.reports import Report
from aegis_db.models.weather import WeatherObservation
from aegis_db.models.timeseries import SensorReading, MachineStateHistory, WorkerLocationHistory
from aegis_db.models.knowledge import KnowledgeDocument

__all__ = [
    "Role", "EquipmentType", "SensorType", "PermitType", "MaintenanceType", "Employer",
    "Plant", "Building", "Zone",
    "Equipment", "Machine", "Sensor",
    "User", "Worker", "UserRoleScope", "Shift", "ShiftAssignment",
    "RefreshToken", "PasswordResetToken",
    "Permit",
    "MaintenanceRecord",
    "Incident", "IncidentTimelineEvent",
    "RiskScore", "Prediction",
    "Alert",
    "Playbook", "PlaybookStep", "EmergencyEvent", "EmergencyEventStep",
    "Camera", "CameraEvent", "PPEViolation",
    "AuditLog",
    "Notification",
    "Report",
    "WeatherObservation",
    "SensorReading", "MachineStateHistory", "WorkerLocationHistory",
    "KnowledgeDocument",
]
