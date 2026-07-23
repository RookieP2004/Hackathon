import { fromSimulatorSeverity, type DashboardSeverity } from '@/components/dashboard/severity';
import type { MapObjectKind } from '@/components/factory-map/types';
import type { TelemetrySnapshot } from '@/lib/services/simulator';

export interface InspectorReading {
  label: string;
  value: string;
}

export interface InspectorWorker {
  worker_id: string;
  name: string;
  badge_id: string;
  status: string;
}

export interface InspectorContent {
  kind: MapObjectKind;
  title: string;
  subtitle: string;
  status: string;
  severity: DashboardSeverity;
  health: number | null;
  alerts: string[];
  liveData: InspectorReading[];
  workersPresent: InspectorWorker[];
}

const READING_LABELS: Record<string, string> = {
  temperature_c: 'Temperature',
  humidity_pct: 'Humidity',
  gas_pct_lel: 'Gas',
  smoke_pct_obscuration: 'Smoke',
  noise_db: 'Noise',
  pressure_bar: 'Pressure',
  vibration_mm_s: 'Vibration',
  current_a: 'Current',
  voltage_v: 'Voltage',
  rpm: 'RPM',
  oil_level_pct: 'Oil Level',
  valve_position_pct: 'Valve Position',
  water_flow_m3h: 'Water Flow',
};

const READING_UNITS: Record<string, string> = {
  temperature_c: '°C',
  humidity_pct: '%',
  gas_pct_lel: '% LEL',
  smoke_pct_obscuration: '%',
  noise_db: ' dB',
  pressure_bar: ' bar',
  vibration_mm_s: ' mm/s',
  current_a: ' A',
  voltage_v: ' V',
  rpm: ' rpm',
  oil_level_pct: '%',
  valve_position_pct: '%',
  water_flow_m3h: ' m³/h',
};

function formatReadings(readings: Record<string, number>): InspectorReading[] {
  return Object.entries(readings).map(([key, value]) => ({
    label: READING_LABELS[key] ?? key,
    value: `${value.toFixed(1)}${READING_UNITS[key] ?? ''}`,
  }));
}

function healthFromSeverity(severity: DashboardSeverity): number {
  switch (severity) {
    case 'nominal':
      return 100;
    case 'low':
      return 85;
    case 'medium':
      return 65;
    case 'high':
      return 40;
    case 'critical':
      return 15;
  }
}

function scenarioAlerts(snapshot: TelemetrySnapshot, predicate: (sc: TelemetrySnapshot['active_scenarios'][number]) => boolean): string[] {
  return snapshot.active_scenarios
    .filter(predicate)
    .map((sc) => `${sc.scenario_type.replace(/_/g, ' ')} — ${sc.phase} (${Math.round(sc.elapsed_seconds)}s)`);
}

function workersInZone(snapshot: TelemetrySnapshot, zoneId: string, exclude?: string): InspectorWorker[] {
  return snapshot.workers
    .filter((w) => w.zone_id === zoneId && w.worker_id !== exclude)
    .map((w) => ({ worker_id: w.worker_id, name: w.name, badge_id: w.badge_id, status: w.status }));
}

export function resolveInspectorContent(
  kind: MapObjectKind,
  id: string,
  snapshot: TelemetrySnapshot,
): InspectorContent | null {
  switch (kind) {
    case 'building': {
      const building = snapshot.buildings.find((b) => b.building_id === id);
      if (!building) return null;
      const severity = fromSimulatorSeverity(building.severity);
      const workers = snapshot.workers.filter((w) => building.zone_ids.includes(w.zone_id));
      return {
        kind,
        title: building.name,
        subtitle: `${building.zone_ids.length} zone${building.zone_ids.length === 1 ? '' : 's'}`,
        status: building.severity,
        severity,
        health: healthFromSeverity(severity),
        alerts: scenarioAlerts(snapshot, (sc) => building.zone_ids.includes(sc.zone_id)),
        liveData: [],
        workersPresent: workers.map((w) => ({ worker_id: w.worker_id, name: w.name, badge_id: w.badge_id, status: w.status })),
      };
    }

    case 'zone': {
      const zone = snapshot.zones.find((z) => z.zone_id === id);
      if (!zone) return null;
      const severity = fromSimulatorSeverity(zone.severity);
      return {
        kind,
        title: zone.name,
        subtitle: `Mode: ${zone.mode}`,
        status: zone.mode,
        severity,
        health: healthFromSeverity(severity),
        alerts: scenarioAlerts(snapshot, (sc) => sc.zone_id === id),
        liveData: formatReadings(zone.ambient as unknown as Record<string, number>),
        workersPresent: workersInZone(snapshot, id),
      };
    }

    case 'machine': {
      const zone = snapshot.zones.find((z) => z.equipment.some((e) => e.equipment_id === id));
      const eq = zone?.equipment.find((e) => e.equipment_id === id);
      if (!zone || !eq) return null;
      const severity = fromSimulatorSeverity(eq.severity);
      return {
        kind,
        title: eq.name,
        subtitle: `${eq.tag} · ${eq.machine_class.replace(/_/g, ' ')} · ${zone.name}`,
        status: eq.status,
        severity,
        health: healthFromSeverity(severity),
        alerts: scenarioAlerts(snapshot, (sc) => sc.equipment_id === id),
        liveData: formatReadings(eq.readings),
        workersPresent: workersInZone(snapshot, zone.zone_id),
      };
    }

    case 'worker': {
      const worker = snapshot.workers.find((w) => w.worker_id === id);
      if (!worker) return null;
      const severity = fromSimulatorSeverity(worker.severity);
      return {
        kind,
        title: worker.name,
        subtitle: `${worker.badge_id} · ${worker.zone_id.replace(/-/g, ' ')}`,
        status: worker.status,
        severity,
        health: healthFromSeverity(severity),
        alerts: scenarioAlerts(snapshot, (sc) => sc.worker_id === id),
        liveData: [
          { label: 'Heart Rate', value: `${worker.vitals.heart_rate_bpm.toFixed(0)} bpm` },
          { label: 'Stress Index', value: worker.vitals.stress_index.toFixed(0) },
          { label: 'Body Temperature', value: `${worker.vitals.body_temperature_c.toFixed(1)}°C` },
        ],
        workersPresent: workersInZone(snapshot, worker.zone_id, id),
      };
    }

    case 'vehicle': {
      const vehicle = snapshot.vehicles.find((v) => v.vehicle_id === id);
      if (!vehicle) return null;
      return {
        kind,
        title: vehicle.name,
        subtitle: `${vehicle.vehicle_type.replace(/_/g, ' ')} · ${vehicle.zone_id.replace(/-/g, ' ')}`,
        status: vehicle.status,
        severity: 'nominal',
        health: null,
        alerts: [],
        liveData: [
          { label: 'Latitude', value: vehicle.gps.lat.toFixed(6) },
          { label: 'Longitude', value: vehicle.gps.lon.toFixed(6) },
        ],
        workersPresent: workersInZone(snapshot, vehicle.zone_id),
      };
    }

    case 'exit': {
      const ex = snapshot.emergency_exits.find((e) => e.exit_id === id);
      if (!ex) return null;
      const severity: DashboardSeverity = ex.status === 'blocked' ? 'critical' : 'nominal';
      return {
        kind,
        title: ex.name,
        subtitle: ex.zone_id.replace(/-/g, ' '),
        status: ex.status,
        severity,
        health: healthFromSeverity(severity),
        alerts: ex.status === 'blocked' ? [`Blocked — active fire/explosion in ${ex.zone_id.replace(/-/g, ' ')}`] : [],
        liveData: [],
        workersPresent: workersInZone(snapshot, ex.zone_id),
      };
    }

    case 'fireSystem': {
      const fs = snapshot.fire_systems.find((f) => f.fire_system_id === id);
      if (!fs) return null;
      const severity: DashboardSeverity = fs.status === 'fault' ? 'critical' : fs.status === 'discharged' ? 'high' : 'nominal';
      return {
        kind,
        title: fs.name,
        subtitle: `${fs.system_type} · ${fs.zone_id.replace(/-/g, ' ')}`,
        status: fs.status,
        severity,
        health: healthFromSeverity(severity),
        alerts: fs.status === 'discharged' ? [`${fs.name} has discharged`] : [],
        liveData: [{ label: 'Lifetime Discharges', value: String(fs.discharge_count) }],
        workersPresent: workersInZone(snapshot, fs.zone_id),
      };
    }

    case 'gasSensor': {
      const zone = snapshot.zones.find((z) => z.zone_id === id);
      if (!zone) return null;
      const severity = fromSimulatorSeverity(zone.ambient_severity);
      return {
        kind,
        title: `${zone.name} Gas Sensor`,
        subtitle: zone.zone_id.replace(/-/g, ' '),
        status: zone.ambient_severity,
        severity,
        health: healthFromSeverity(severity),
        alerts: severity !== 'nominal' ? [`Gas concentration at ${zone.ambient.gas_pct_lel.toFixed(1)}% LEL`] : [],
        liveData: [{ label: 'Gas Concentration', value: `${zone.ambient.gas_pct_lel.toFixed(1)}% LEL` }],
        workersPresent: workersInZone(snapshot, zone.zone_id),
      };
    }

    case 'camera': {
      const zone = snapshot.zones.find((z) => z.zone_id === id);
      if (!zone) return null;
      const eventSeverity: DashboardSeverity =
        zone.camera.event_type === 'normal'
          ? 'nominal'
          : ['fire_detected', 'explosion_detected', 'person_down'].includes(zone.camera.event_type)
            ? 'critical'
            : 'medium';
      return {
        kind,
        title: `${zone.name} Camera`,
        subtitle: zone.camera.camera_id,
        status: zone.camera.event_type.replace(/_/g, ' '),
        severity: eventSeverity,
        health: healthFromSeverity(eventSeverity),
        alerts: zone.camera.event_type !== 'normal' ? [`Detected: ${zone.camera.event_type.replace(/_/g, ' ')}`] : [],
        liveData: [
          { label: 'Confidence', value: `${Math.round(zone.camera.confidence * 100)}%` },
          { label: 'Person Count', value: String(zone.camera.person_count) },
        ],
        workersPresent: workersInZone(snapshot, zone.zone_id),
      };
    }

    case 'pipeline': {
      const pipe = snapshot.pipelines.find((p) => p.pipeline_id === id);
      if (!pipe) return null;
      const severity = fromSimulatorSeverity(pipe.severity);
      const workers = [
        ...workersInZone(snapshot, pipe.from_zone_id),
        ...(pipe.to_zone_id !== pipe.from_zone_id ? workersInZone(snapshot, pipe.to_zone_id) : []),
      ];
      return {
        kind,
        title: pipe.name,
        subtitle: `${pipe.kind} line · ${pipe.from_equipment_id} → ${pipe.to_equipment_id}`,
        status: pipe.status,
        severity,
        health: healthFromSeverity(severity),
        alerts: pipe.status === 'stopped' ? [`${pipe.name} has stopped flowing`] : [],
        liveData: [
          { label: 'Flow Status', value: pipe.status },
          { label: 'Line Type', value: pipe.kind },
        ],
        workersPresent: workers,
      };
    }

    case 'robot': {
      const robot = snapshot.robots.find((r) => r.robot_id === id);
      if (!robot) return null;
      const severity: DashboardSeverity = robot.status === 'fault' ? 'critical' : 'nominal';
      return {
        kind,
        title: robot.name,
        subtitle: `${robot.robot_type === 'arm' ? 'Robotic arm' : 'Autonomous mobile robot'} · ${robot.zone_id.replace(/-/g, ' ')}`,
        status: robot.status,
        severity,
        health: healthFromSeverity(severity),
        alerts: robot.status === 'fault' ? [`${robot.name} has faulted`] : [],
        liveData:
          robot.robot_type === 'arm'
            ? [{ label: 'Cycle Phase', value: `${Math.round(robot.cycle_phase * 100)}%` }]
            : [
                { label: 'Latitude', value: robot.gps.lat.toFixed(6) },
                { label: 'Longitude', value: robot.gps.lon.toFixed(6) },
              ],
        workersPresent: workersInZone(snapshot, robot.zone_id),
      };
    }

    case 'emergencyResponder': {
      const responder = snapshot.emergency_responders.find((r) => r.responder_id === id);
      if (!responder) return null;
      const severity: DashboardSeverity = responder.status === 'standby' ? 'nominal' : 'high';
      return {
        kind,
        title: responder.name,
        subtitle: `Muster point: ${responder.home_zone_id.replace(/-/g, ' ')}`,
        status: responder.status,
        severity,
        health: healthFromSeverity(severity),
        alerts: responder.status !== 'standby' ? [`${responder.name} is ${responder.status.replace('_', ' ')}`] : [],
        liveData: [
          { label: 'Latitude', value: responder.gps.lat.toFixed(6) },
          { label: 'Longitude', value: responder.gps.lon.toFixed(6) },
        ],
        workersPresent: [],
      };
    }

    default:
      return null;
  }
}
