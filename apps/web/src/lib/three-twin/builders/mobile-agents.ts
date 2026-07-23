import * as THREE from 'three';
import { indexOffset, mobileBasePosition } from '@/lib/factory-map-layout';
import { toWorldX, toWorldZ, zoneWorldRect } from '@/lib/three-twin/coordinates';
import { createTextSprite, updateTextSprite } from '@/lib/three-twin/text-sprite';
import { SEVERITY_HEX } from '@/lib/three-twin/severity-colors';
import { fromSimulatorSeverity } from '@/components/dashboard/severity';
import { offsetFromAnchor, type AnchorRegistry } from '@/lib/mobile-position';
import type { EmergencyResponderSnapshot, TelemetrySnapshot, WorldTopology } from '@/lib/services/simulator';

function humanoidMesh(color: string): { group: THREE.Group; body: THREE.MeshStandardMaterial } {
  const group = new THREE.Group();
  const body = new THREE.MeshStandardMaterial({ color });
  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.28, 0.7, 4, 8), body);
  torso.position.y = 1.0;
  torso.castShadow = true;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.22, 12, 10), body);
  head.position.y = 1.55;
  head.castShadow = true;
  group.add(torso, head);
  return { group, body };
}

function forkliftMesh(): { group: THREE.Group; body: THREE.MeshStandardMaterial } {
  const group = new THREE.Group();
  const body = new THREE.MeshStandardMaterial({ color: '#E8C547', roughness: 0.5 });
  const chassis = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.7, 1.8), body);
  chassis.position.y = 0.5;
  chassis.castShadow = true;
  const mast = new THREE.Mesh(new THREE.BoxGeometry(0.15, 1.6, 0.15), new THREE.MeshStandardMaterial({ color: '#9AA4B2' }));
  mast.position.set(0, 0.9, 0.9);
  group.add(chassis, mast);
  return { group, body };
}

function tankerMesh(): { group: THREE.Group; body: THREE.MeshStandardMaterial } {
  const group = new THREE.Group();
  const body = new THREE.MeshStandardMaterial({ color: '#6E8FAE', roughness: 0.4, metalness: 0.3 });
  const tank = new THREE.Mesh(new THREE.CylinderGeometry(0.75, 0.75, 2.6, 16), body);
  tank.rotation.z = Math.PI / 2;
  tank.position.y = 0.9;
  tank.castShadow = true;
  group.add(tank);
  return { group, body };
}

function armRobotMesh(): { group: THREE.Group; body: THREE.MeshStandardMaterial; arm: THREE.Object3D | null } {
  const group = new THREE.Group();
  const body = new THREE.MeshStandardMaterial({ color: '#4F5FE8', roughness: 0.4, metalness: 0.5 });
  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.5, 0.4, 16), body);
  base.position.y = 0.2;
  const armPivot = new THREE.Group();
  armPivot.position.y = 0.4;
  const upperArm = new THREE.Mesh(new THREE.BoxGeometry(0.25, 1.2, 0.25), body);
  upperArm.position.y = 0.6;
  armPivot.add(upperArm);
  group.add(base, armPivot);
  return { group, body, arm: armPivot as THREE.Object3D | null };
}

function amrRobotMesh(): { group: THREE.Group; body: THREE.MeshStandardMaterial; arm: THREE.Object3D | null } {
  const group = new THREE.Group();
  const body = new THREE.MeshStandardMaterial({ color: '#3CD8E8', emissive: '#3CD8E8', emissiveIntensity: 0.3 });
  const puck = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.4, 0.3, 20), body);
  puck.position.y = 0.2;
  puck.castShadow = true;
  group.add(puck);
  return { group, body, arm: null };
}

function responderMesh(): { group: THREE.Group; body: THREE.MeshStandardMaterial } {
  const group = new THREE.Group();
  const body = new THREE.MeshStandardMaterial({ color: '#E5484D' });
  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.3, 0.75, 4, 8), body);
  torso.position.y = 1.05;
  torso.castShadow = true;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.24, 12, 10), new THREE.MeshStandardMaterial({ color: '#F5A524' })); // hi-vis helmet
  head.position.y = 1.65;
  group.add(torso, head);
  return { group, body };
}

interface AgentEntry<TStatus extends string = string> {
  group: THREE.Group;
  body: THREE.MeshStandardMaterial;
  label: THREE.Sprite;
  lastLabelText: string;
  arm?: THREE.Object3D;
  lastStatus?: TStatus;
}

export interface MobileAgentRefs {
  group: THREE.Group;
  workers: Map<string, AgentEntry>;
  vehicles: Map<string, AgentEntry>;
  robots: Map<string, AgentEntry>;
  responders: Map<string, AgentEntry>;
}

export function buildMobileAgents(world: WorldTopology): MobileAgentRefs {
  const group = new THREE.Group();
  group.name = 'mobile-agents';
  const workers = new Map<string, AgentEntry>();
  const vehicles = new Map<string, AgentEntry>();
  const robots = new Map<string, AgentEntry>();
  const responders = new Map<string, AgentEntry>();

  for (const worker of world.workers) {
    const { group: mesh, body } = humanoidMesh('#6E8FAE');
    const label = createTextSprite(worker.name.split(' ')[0] ?? worker.name, { fontSize: 30 });
    label.position.y = 2.1;
    mesh.add(label);
    mesh.userData.mapObjectKind = 'worker';
    mesh.userData.mapObjectId = worker.worker_id;
    mesh.traverse((c) => {
      c.userData.mapObjectKind = 'worker';
      c.userData.mapObjectId = worker.worker_id;
    });
    group.add(mesh);
    workers.set(worker.worker_id, { group: mesh, body, label, lastLabelText: worker.name });
  }

  for (const vehicle of world.vehicles) {
    const { group: mesh, body } = vehicle.vehicle_type === 'forklift' ? forkliftMesh() : tankerMesh();
    const label = createTextSprite(vehicle.name, { fontSize: 28 });
    label.position.y = 2.2;
    mesh.add(label);
    mesh.userData.mapObjectKind = 'vehicle';
    mesh.userData.mapObjectId = vehicle.vehicle_id;
    mesh.traverse((c) => {
      c.userData.mapObjectKind = 'vehicle';
      c.userData.mapObjectId = vehicle.vehicle_id;
    });
    group.add(mesh);
    vehicles.set(vehicle.vehicle_id, { group: mesh, body, label, lastLabelText: vehicle.name });
  }

  for (const robot of world.robots) {
    const built = robot.robot_type === 'arm' ? armRobotMesh() : amrRobotMesh();
    const label = createTextSprite(robot.name, { fontSize: 28, color: '#3CD8E8' });
    label.position.y = robot.robot_type === 'arm' ? 2.4 : 1.2;
    built.group.add(label);
    built.group.userData.mapObjectKind = 'robot';
    built.group.userData.mapObjectId = robot.robot_id;
    built.group.traverse((c) => {
      c.userData.mapObjectKind = 'robot';
      c.userData.mapObjectId = robot.robot_id;
    });
    group.add(built.group);
    robots.set(robot.robot_id, { group: built.group, body: built.body, label, lastLabelText: robot.name, arm: built.arm ?? undefined });
  }

  for (const responder of world.emergency_responders) {
    const { group: mesh, body } = responderMesh();
    const label = createTextSprite(responder.name, { fontSize: 28, color: '#E5484D' });
    label.position.y = 2.2;
    mesh.add(label);
    mesh.userData.mapObjectKind = 'emergencyResponder';
    mesh.userData.mapObjectId = responder.responder_id;
    mesh.traverse((c) => {
      c.userData.mapObjectKind = 'emergencyResponder';
      c.userData.mapObjectId = responder.responder_id;
    });
    group.add(mesh);
    responders.set(responder.responder_id, { group: mesh, body, label, lastLabelText: responder.name });
  }

  return { group, workers, vehicles, robots, responders };
}

function placeInZone(zoneId: string, agentIndex: number, indexSeed: number, offsetPx: { dx: number; dy: number }): { x: number; z: number } {
  const base = mobileBasePosition(zoneId);
  const spread = indexOffset(indexSeed + agentIndex);
  return {
    x: toWorldX(base.x + spread.x + offsetPx.dx),
    z: toWorldZ(base.y + spread.y + offsetPx.dy),
  };
}

export function updateMobileAgents(
  refs: MobileAgentRefs,
  snapshot: TelemetrySnapshot,
  anchors: AnchorRegistry,
  deltaSeconds: number,
) {
  const zoneCounters = new Map<string, number>();
  const counterFor = (zoneId: string) => {
    const n = zoneCounters.get(zoneId) ?? 0;
    zoneCounters.set(zoneId, n + 1);
    return n;
  };

  for (const worker of snapshot.workers) {
    const entry = refs.workers.get(worker.worker_id);
    if (!entry) continue;
    updateHumanoidLike(entry, worker.name, worker.status, worker.severity, worker.status === 'collapsed');
    const offset = offsetFromAnchor(anchors, `worker:${worker.worker_id}`, worker.gps.lat, worker.gps.lon);
    const idx = counterFor(`w:${worker.zone_id}`);
    const { x, z } = placeInZone(worker.zone_id, idx, 0, offset);
    if (worker.status === 'collapsed') {
      entry.group.rotation.z = THREE.MathUtils.lerp(entry.group.rotation.z, Math.PI / 2, 0.15);
      entry.group.position.y = THREE.MathUtils.lerp(entry.group.position.y, 0, 0.15);
    } else {
      entry.group.rotation.z = THREE.MathUtils.lerp(entry.group.rotation.z, 0, 0.15);
      entry.group.position.y = 0;
    }
    entry.group.position.x = THREE.MathUtils.lerp(entry.group.position.x, x, 0.15);
    entry.group.position.z = THREE.MathUtils.lerp(entry.group.position.z, z, 0.15);
  }

  for (const vehicle of snapshot.vehicles) {
    const entry = refs.vehicles.get(vehicle.vehicle_id);
    if (!entry) continue;
    const offset = offsetFromAnchor(anchors, `vehicle:${vehicle.vehicle_id}`, vehicle.gps.lat, vehicle.gps.lon);
    const idx = counterFor(`v:${vehicle.zone_id}`);
    const { x, z } = placeInZone(vehicle.zone_id, idx, 3, offset);
    const dx = x - entry.group.position.x;
    const dz = z - entry.group.position.z;
    if (Math.abs(dx) > 0.001 || Math.abs(dz) > 0.001) {
      entry.group.rotation.y = Math.atan2(dx, dz);
    }
    entry.group.position.x = THREE.MathUtils.lerp(entry.group.position.x, x, 0.12);
    entry.group.position.z = THREE.MathUtils.lerp(entry.group.position.z, z, 0.12);
  }

  for (const robot of snapshot.robots) {
    const entry = refs.robots.get(robot.robot_id);
    if (!entry) continue;
    if (robot.robot_type === 'arm') {
      if (entry.arm) {
        const swing = Math.sin(robot.cycle_phase * Math.PI * 2) * 0.9;
        entry.arm.rotation.x = robot.status === 'fault' ? entry.arm.rotation.x : swing;
      }
      const faulted = robot.status === 'fault';
      entry.body.emissive.set(faulted ? SEVERITY_HEX.critical : '#4F5FE8');
      entry.body.emissiveIntensity = faulted ? 0.5 : 0.15;
    } else {
      const offset = offsetFromAnchor(anchors, `robot:${robot.robot_id}`, robot.gps.lat, robot.gps.lon);
      const idx = counterFor(`amr:${robot.zone_id}`);
      const { x, z } = placeInZone(robot.zone_id, idx, 6, offset);
      entry.group.position.x = THREE.MathUtils.lerp(entry.group.position.x, x, 0.12);
      entry.group.position.z = THREE.MathUtils.lerp(entry.group.position.z, z, 0.12);
      entry.group.rotation.y += deltaSeconds * 0.6; // AMRs read as "scanning" while idle/moving
    }
  }

  const emergencyZoneId = snapshot.active_scenarios[0]?.zone_id ?? null;
  for (const responder of snapshot.emergency_responders) {
    const entry = refs.responders.get(responder.responder_id);
    if (!entry) continue;
    updateResponderPosition(entry, responder, emergencyZoneId, anchors);
    if (entry.lastStatus !== responder.status) {
      updateTextSprite(entry.label, `${responder.name} (${responder.status})`, { fontSize: 28, color: '#E5484D' });
      entry.lastStatus = responder.status;
    }
  }
}

function updateHumanoidLike(entry: AgentEntry, name: string, status: string, severity: string, collapsed: boolean) {
  const color = collapsed ? SEVERITY_HEX.critical : SEVERITY_HEX[fromSimulatorSeverity(severity as 'normal' | 'warning' | 'critical')];
  entry.body.color.set(color);
  if (entry.lastStatus !== status) {
    updateTextSprite(entry.label, collapsed ? `${name.split(' ')[0]} (down)` : (name.split(' ')[0] ?? name), { fontSize: 30 });
    entry.lastStatus = status;
  }
}

const RESPONDER_TRAVEL_REFERENCE_DEG = 0.0018; // empirically ~ the lat/lon span between the demo world's farthest zones

function updateResponderPosition(
  entry: AgentEntry,
  responder: EmergencyResponderSnapshot,
  emergencyZoneId: string | null,
  anchors: AnchorRegistry,
) {
  const homeRect = zoneWorldRect(responder.home_zone_id);
  const targetZoneId = emergencyZoneId ?? responder.home_zone_id;
  const targetRect = zoneWorldRect(targetZoneId);

  let progress: number;
  if (responder.status === 'standby') {
    progress = 0;
  } else if (responder.status === 'on_scene') {
    progress = 1;
  } else {
    // "responding": approximate progress from how far their live lat/lon has
    // moved from their very-first-seen position (== home, since they start
    // there) — an approximation, not a precise re-derivation of the engine's
    // internal zone-anchor math, but visually reads as genuine travel.
    const offset = offsetFromAnchor(anchors, `responder:${responder.responder_id}`, responder.gps.lat, responder.gps.lon);
    const magnitudeDeg = Math.hypot(offset.dx, offset.dy) / 500_000; // undo offsetFromAnchor's pixel scaling to get back to degrees
    progress = THREE.MathUtils.clamp(magnitudeDeg / RESPONDER_TRAVEL_REFERENCE_DEG, 0, 1);
  }

  const x = THREE.MathUtils.lerp(homeRect.centerX, targetRect.centerX, progress);
  const z = THREE.MathUtils.lerp(homeRect.centerZ, targetRect.centerZ, progress);
  entry.group.position.x = THREE.MathUtils.lerp(entry.group.position.x, x, 0.08);
  entry.group.position.z = THREE.MathUtils.lerp(entry.group.position.z, z, 0.08);
}
