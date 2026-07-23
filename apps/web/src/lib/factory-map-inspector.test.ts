import { describe, expect, it } from 'vitest';
import { resolveInspectorContent } from './factory-map-inspector';
import type { TelemetrySnapshot } from './services/simulator';

const snapshot: TelemetrySnapshot = {
  type: 'telemetry',
  tick: 10,
  timestamp: Date.now() / 1000,
  global_mode: 'normal',
  active_scenarios: [
    { scenario_type: 'fire', zone_id: 'boiler-room', equipment_id: null, worker_id: null, phase: 'escalation', elapsed_seconds: 20 },
  ],
  buildings: [{ building_id: 'utilities-building', name: 'Utilities Building', zone_ids: ['compressor-house', 'boiler-room'], severity: 'critical' }],
  zones: [
    {
      zone_id: 'boiler-room',
      name: 'Boiler Room',
      building_id: 'utilities-building',
      mode: 'normal',
      severity: 'critical',
      ambient_severity: 'critical',
      ambient: { temperature_c: 90, humidity_pct: 40, gas_pct_lel: 3, smoke_pct_obscuration: 60, noise_db: 90 },
      equipment: [
        { equipment_id: 'eq-b201', tag: 'B-201', name: 'Boiler 201', machine_class: 'boiler', status: 'operational', severity: 'warning', readings: { temperature_c: 190, pressure_bar: 12.5 } },
      ],
      camera: { camera_id: 'CAM-02', event_type: 'fire_detected', confidence: 0.9, person_count: 1 },
    },
  ],
  workers: [
    { worker_id: 'w-2', name: 'Suresh Patil', badge_id: 'BADGE-1002', zone_id: 'boiler-room', status: 'active', severity: 'warning', gps: { lat: 19.08, lon: 72.88 }, vitals: { heart_rate_bpm: 95, stress_index: 55, body_temperature_c: 37.1 } },
  ],
  vehicles: [
    { vehicle_id: 'veh-3', name: 'Tanker Truck 1', vehicle_type: 'tanker_truck', zone_id: 'tank-farm', status: 'idle', gps: { lat: 19.08, lon: 72.88 } },
  ],
  emergency_exits: [{ exit_id: 'exit-2', name: 'Boiler Room Exit A', zone_id: 'boiler-room', status: 'blocked' }],
  fire_systems: [{ fire_system_id: 'fs-2', name: 'Boiler Room Deluge', zone_id: 'boiler-room', system_type: 'deluge', status: 'discharged', discharge_count: 2 }],
  pipelines: [
    {
      pipeline_id: 'pipe-2',
      name: 'Valve 12 to Boiler Feed',
      kind: 'feed',
      from_equipment_id: 'eq-v12',
      to_equipment_id: 'eq-b201',
      from_zone_id: 'tank-farm',
      to_zone_id: 'boiler-room',
      status: 'stopped',
      severity: 'critical',
    },
  ],
  robots: [
    { robot_id: 'robot-1', name: 'Assembly Arm 1', robot_type: 'arm', zone_id: 'boiler-room', equipment_id: 'eq-b201', status: 'fault', cycle_phase: 0.4, gps: { lat: 19.08, lon: 72.88 } },
  ],
  emergency_responders: [
    { responder_id: 'resp-1', name: 'Fire Team Alpha', home_zone_id: 'warehouse', status: 'responding', gps: { lat: 19.08, lon: 72.88 } },
  ],
};

describe('resolveInspectorContent', () => {
  it('resolves a building with aggregated worker presence and alerts', () => {
    const content = resolveInspectorContent('building', 'utilities-building', snapshot);
    expect(content?.severity).toBe('critical');
    expect(content?.workersPresent).toHaveLength(1);
    expect(content?.alerts[0]).toMatch(/fire/);
  });

  it('resolves a zone with ambient readings as live data', () => {
    const content = resolveInspectorContent('zone', 'boiler-room', snapshot);
    expect(content?.status).toBe('normal'); // zone.mode
    expect(content?.liveData.find((r) => r.label === 'Temperature')?.value).toBe('90.0°C');
  });

  it('resolves a machine with its own readings and zone worker presence', () => {
    const content = resolveInspectorContent('machine', 'eq-b201', snapshot);
    expect(content?.title).toBe('Boiler 201');
    expect(content?.liveData.find((r) => r.label === 'Pressure')?.value).toBe('12.5 bar');
    expect(content?.workersPresent).toHaveLength(1);
  });

  it('resolves a worker and excludes themselves from workersPresent', () => {
    const content = resolveInspectorContent('worker', 'w-2', snapshot);
    expect(content?.title).toBe('Suresh Patil');
    expect(content?.workersPresent).toHaveLength(0); // only worker in the zone is themself
  });

  it('resolves a vehicle with no severity concept (always nominal)', () => {
    const content = resolveInspectorContent('vehicle', 'veh-3', snapshot);
    expect(content?.severity).toBe('nominal');
    expect(content?.health).toBeNull();
  });

  it('resolves a blocked emergency exit as critical with an alert', () => {
    const content = resolveInspectorContent('exit', 'exit-2', snapshot);
    expect(content?.severity).toBe('critical');
    expect(content?.alerts).toHaveLength(1);
  });

  it('resolves a discharged fire system as high severity with discharge count', () => {
    const content = resolveInspectorContent('fireSystem', 'fs-2', snapshot);
    expect(content?.severity).toBe('high');
    expect(content?.liveData[0]?.value).toBe('2');
  });

  it('resolves a gas sensor from the zone ambient reading', () => {
    const content = resolveInspectorContent('gasSensor', 'boiler-room', snapshot);
    expect(content?.severity).toBe('critical');
    expect(content?.liveData[0]?.value).toBe('3.0% LEL');
  });

  it('resolves a camera and flags a non-normal event as critical', () => {
    const content = resolveInspectorContent('camera', 'boiler-room', snapshot);
    expect(content?.severity).toBe('critical');
    expect(content?.status).toBe('fire detected');
  });

  it('resolves a stopped pipeline as critical with an alert and combined worker presence from both zones', () => {
    const content = resolveInspectorContent('pipeline', 'pipe-2', snapshot);
    expect(content?.severity).toBe('critical');
    expect(content?.status).toBe('stopped');
    expect(content?.alerts).toHaveLength(1);
    // pipe-2 spans tank-farm -> boiler-room; only boiler-room has a worker in this fixture.
    expect(content?.workersPresent.map((w) => w.worker_id)).toEqual(['w-2']);
  });

  it('resolves a faulted arm robot as critical with an alert', () => {
    const content = resolveInspectorContent('robot', 'robot-1', snapshot);
    expect(content?.severity).toBe('critical');
    expect(content?.alerts).toHaveLength(1);
    expect(content?.liveData[0]).toEqual({ label: 'Cycle Phase', value: '40%' });
  });

  it('resolves a responding emergency responder as high severity with an alert', () => {
    const content = resolveInspectorContent('emergencyResponder', 'resp-1', snapshot);
    expect(content?.severity).toBe('high');
    expect(content?.status).toBe('responding');
    expect(content?.alerts).toHaveLength(1);
  });

  it('returns null for an unknown id', () => {
    expect(resolveInspectorContent('machine', 'does-not-exist', snapshot)).toBeNull();
  });
});
