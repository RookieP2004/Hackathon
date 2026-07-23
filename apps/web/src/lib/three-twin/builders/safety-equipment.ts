import * as THREE from 'three';
import { exitPosition, fireSystemPosition } from '@/lib/factory-map-layout';
import { toWorldX, toWorldZ } from '@/lib/three-twin/coordinates';
import { SEVERITY_HEX } from '@/lib/three-twin/severity-colors';
import type { EmergencyExitSnapshot, FireSystemSnapshot, WorldTopology } from '@/lib/services/simulator';

interface ExitEntry {
  material: THREE.MeshStandardMaterial;
}

interface FireSystemEntry {
  material: THREE.MeshStandardMaterial;
  head: THREE.Mesh;
}

export interface SafetyEquipmentRefs {
  group: THREE.Group;
  exits: Map<string, ExitEntry>;
  fireSystems: Map<string, FireSystemEntry>;
}

export function buildSafetyEquipment(world: WorldTopology): SafetyEquipmentRefs {
  const group = new THREE.Group();
  group.name = 'safety-equipment';
  const exits = new Map<string, ExitEntry>();
  const fireSystems = new Map<string, FireSystemEntry>();

  const exitsByZone = new Map<string, typeof world.emergency_exits>();
  for (const ex of world.emergency_exits) {
    const list = exitsByZone.get(ex.zone_id) ?? [];
    list.push(ex);
    exitsByZone.set(ex.zone_id, list);
  }
  for (const [zoneId, list] of exitsByZone) {
    list.forEach((ex, index) => {
      const pos = exitPosition(zoneId, index, list.length);
      const material = new THREE.MeshStandardMaterial({ color: SEVERITY_HEX.nominal, emissive: SEVERITY_HEX.nominal, emissiveIntensity: 0.5 });
      const frame = new THREE.Mesh(new THREE.BoxGeometry(1.2, 2.2, 0.15), material);
      frame.position.set(toWorldX(pos.x), 1.1, toWorldZ(pos.y));
      frame.userData.mapObjectKind = 'exit';
      frame.userData.mapObjectId = ex.exit_id;
      group.add(frame);
      exits.set(ex.exit_id, { material });
    });
  }

  for (const fs of world.fire_systems) {
    const pos = fireSystemPosition(fs.zone_id);
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 1.8, 8), new THREE.MeshStandardMaterial({ color: '#5B6472' }));
    pole.position.set(toWorldX(pos.x), 0.9, toWorldZ(pos.y));
    group.add(pole);

    const material = new THREE.MeshStandardMaterial({ color: SEVERITY_HEX.nominal, emissive: SEVERITY_HEX.nominal, emissiveIntensity: 0.6 });
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.28, 12, 10), material);
    head.position.set(toWorldX(pos.x), 1.9, toWorldZ(pos.y));
    head.userData.mapObjectKind = 'fireSystem';
    head.userData.mapObjectId = fs.fire_system_id;
    group.add(head);
    fireSystems.set(fs.fire_system_id, { material, head });
  }

  return { group, exits, fireSystems };
}

export function updateSafetyEquipment(
  refs: SafetyEquipmentRefs,
  exits: EmergencyExitSnapshot[],
  fireSystems: FireSystemSnapshot[],
  elapsedSeconds: number,
) {
  for (const ex of exits) {
    const entry = refs.exits.get(ex.exit_id);
    if (!entry) continue;
    const blocked = ex.status === 'blocked';
    const color = blocked ? SEVERITY_HEX.critical : SEVERITY_HEX.nominal;
    entry.material.color.set(color);
    entry.material.emissive.set(color);
    entry.material.emissiveIntensity = blocked ? 0.6 + Math.abs(Math.sin(elapsedSeconds * 6)) * 0.5 : 0.5;
  }

  for (const fs of fireSystems) {
    const entry = refs.fireSystems.get(fs.fire_system_id);
    if (!entry) continue;
    const color = fs.status === 'discharged' ? SEVERITY_HEX.high : fs.status === 'fault' ? SEVERITY_HEX.critical : SEVERITY_HEX.nominal;
    entry.material.color.set(color);
    entry.material.emissive.set(color);
    entry.material.emissiveIntensity = fs.status === 'discharged' ? 0.7 + Math.abs(Math.sin(elapsedSeconds * 10)) * 0.4 : 0.6;
  }
}
