/** Types + REST control client for the iot-simulator service. */

import { fetchWithAuth } from '@/lib/api-client';

const BASE_URL = process.env.NEXT_PUBLIC_IOT_SIMULATOR_URL ?? 'http://localhost:8014';

export type Severity = 'normal' | 'warning' | 'critical';
export type ScenarioType = 'gas_leak' | 'explosion' | 'machine_failure' | 'worker_collapse' | 'fire';

export interface AmbientReadings {
  temperature_c: number;
  humidity_pct: number;
  gas_pct_lel: number;
  smoke_pct_obscuration: number;
  noise_db: number;
}

export interface CameraState {
  camera_id: string;
  event_type: string;
  confidence: number;
  person_count: number;
}

export interface EquipmentReading {
  equipment_id: string;
  tag: string;
  name: string;
  machine_class: string;
  status: string;
  severity: Severity;
  readings: Record<string, number>;
}

export interface ZoneSnapshot {
  zone_id: string;
  name: string;
  building_id: string;
  mode: Severity;
  severity: Severity;
  ambient_severity: Severity;
  ambient: AmbientReadings;
  equipment: EquipmentReading[];
  camera: CameraState;
}

export interface BuildingSnapshot {
  building_id: string;
  name: string;
  zone_ids: string[];
  severity: Severity;
}

export interface VehicleSnapshot {
  vehicle_id: string;
  name: string;
  vehicle_type: 'forklift' | 'tanker_truck';
  zone_id: string;
  status: 'moving' | 'idle' | 'parked';
  gps: { lat: number; lon: number };
}

export interface EmergencyExitSnapshot {
  exit_id: string;
  name: string;
  zone_id: string;
  status: 'clear' | 'blocked';
}

export interface FireSystemSnapshot {
  fire_system_id: string;
  name: string;
  zone_id: string;
  system_type: 'sprinkler' | 'deluge' | 'foam';
  status: 'armed' | 'discharged' | 'fault';
  discharge_count: number;
}

export interface PipelineSnapshot {
  pipeline_id: string;
  name: string;
  kind: 'process' | 'utility' | 'feed';
  from_equipment_id: string;
  to_equipment_id: string;
  from_zone_id: string;
  to_zone_id: string;
  status: 'flowing' | 'stopped';
  severity: Severity;
}

export interface RobotSnapshot {
  robot_id: string;
  name: string;
  robot_type: 'arm' | 'amr';
  zone_id: string;
  equipment_id: string | null;
  status: 'idle' | 'running' | 'fault' | 'moving';
  cycle_phase: number;
  gps: { lat: number; lon: number };
}

export interface EmergencyResponderSnapshot {
  responder_id: string;
  name: string;
  home_zone_id: string;
  status: 'standby' | 'responding' | 'on_scene';
  gps: { lat: number; lon: number };
}

export interface WorkerVitals {
  heart_rate_bpm: number;
  stress_index: number;
  body_temperature_c: number;
}

export interface WorkerSnapshot {
  worker_id: string;
  name: string;
  badge_id: string;
  zone_id: string;
  status: 'active' | 'collapsed';
  severity: Severity;
  gps: { lat: number; lon: number };
  vitals: WorkerVitals;
}

export interface ActiveScenarioSnapshot {
  scenario_type: ScenarioType;
  zone_id: string;
  equipment_id: string | null;
  worker_id: string | null;
  phase: string;
  elapsed_seconds: number;
}

export interface TelemetrySnapshot {
  type: 'telemetry';
  tick: number;
  timestamp: number;
  global_mode: Severity;
  active_scenarios: ActiveScenarioSnapshot[];
  buildings: BuildingSnapshot[];
  zones: ZoneSnapshot[];
  workers: WorkerSnapshot[];
  vehicles: VehicleSnapshot[];
  emergency_exits: EmergencyExitSnapshot[];
  fire_systems: FireSystemSnapshot[];
  pipelines: PipelineSnapshot[];
  robots: RobotSnapshot[];
  emergency_responders: EmergencyResponderSnapshot[];
}

export interface WorldTopology {
  buildings: Array<{ building_id: string; name: string }>;
  zones: Array<{
    zone_id: string;
    name: string;
    building_id: string;
    camera_id: string;
    equipment: Array<{ equipment_id: string; tag: string; name: string; machine_class: string }>;
  }>;
  workers: Array<{ worker_id: string; name: string; badge_id: string; zone_id: string }>;
  vehicles: Array<{ vehicle_id: string; name: string; vehicle_type: string; zone_id: string }>;
  emergency_exits: Array<{ exit_id: string; name: string; zone_id: string }>;
  fire_systems: Array<{ fire_system_id: string; name: string; zone_id: string; system_type: string }>;
  pipelines: Array<{
    pipeline_id: string;
    name: string;
    kind: string;
    from_equipment_id: string;
    to_equipment_id: string;
  }>;
  robots: Array<{ robot_id: string; name: string; robot_type: string; zone_id: string; equipment_id: string | null }>;
  emergency_responders: Array<{ responder_id: string; name: string; home_zone_id: string }>;
  zone_adjacency: Record<string, string[]>;
  scenario_types: ScenarioType[];
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetchWithAuth(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.error?.message ?? `Simulator request failed (${res.status})`);
  }
  return res.json();
}

export async function fetchWorldTopology(): Promise<WorldTopology> {
  const res = await fetchWithAuth(`${BASE_URL}/world`);
  if (!res.ok) throw new Error(`Failed to fetch world topology (${res.status})`);
  return res.json();
}

export function setSimulatorMode(mode: Severity, zoneId?: string) {
  return postJson('/control/mode', { mode, zone_id: zoneId ?? null });
}

export function triggerScenario(
  scenario: ScenarioType,
  target: { zoneId?: string; equipmentId?: string; workerId?: string },
) {
  return postJson('/control/scenario', {
    scenario,
    zone_id: target.zoneId ?? null,
    equipment_id: target.equipmentId ?? null,
    worker_id: target.workerId ?? null,
  });
}

export function resetSimulator(zoneId?: string) {
  return postJson('/control/reset', { zone_id: zoneId ?? null });
}
