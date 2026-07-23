import * as THREE from 'three';
import { equipmentPosition } from '@/lib/factory-map-layout';
import { toWorldX, toWorldZ } from '@/lib/three-twin/coordinates';
import { createTextSprite } from '@/lib/three-twin/text-sprite';
import { SEVERITY_HEX } from '@/lib/three-twin/severity-colors';
import { fromSimulatorSeverity } from '@/components/dashboard/severity';
import type { WorldTopology, ZoneSnapshot } from '@/lib/services/simulator';

interface MachineEntry {
  group: THREE.Group;
  spinner: THREE.Object3D | null;
  bodyMaterial: THREE.MeshStandardMaterial;
  label: THREE.Sprite;
}

export interface MachineRefs {
  group: THREE.Group;
  byId: Map<string, MachineEntry>;
}

function buildMachineGeometry(machineClass: string): { group: THREE.Group; spinner: THREE.Object3D | null; bodyMaterial: THREE.MeshStandardMaterial } {
  const group = new THREE.Group();
  const bodyMaterial = new THREE.MeshStandardMaterial({ color: '#4b5563', roughness: 0.5, metalness: 0.4 });
  let spinner: THREE.Object3D | null = null;

  switch (machineClass) {
    case 'compressor': {
      const body = new THREE.Mesh(new THREE.CylinderGeometry(1.1, 1.1, 2.6, 20), bodyMaterial);
      body.rotation.z = Math.PI / 2;
      body.position.y = 1.3;
      body.castShadow = true;
      group.add(body);
      const fan = new THREE.Mesh(new THREE.TorusGeometry(0.6, 0.08, 8, 16), new THREE.MeshStandardMaterial({ color: '#9AA4B2' }));
      fan.position.set(1.4, 1.3, 0);
      fan.rotation.y = Math.PI / 2;
      group.add(fan);
      spinner = fan;
      break;
    }
    case 'boiler': {
      const body = new THREE.Mesh(new THREE.CylinderGeometry(1.4, 1.4, 4.5, 20), bodyMaterial);
      body.position.y = 2.25;
      body.castShadow = true;
      group.add(body);
      const dome = new THREE.Mesh(new THREE.SphereGeometry(1.4, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2), bodyMaterial);
      dome.position.y = 4.5;
      group.add(dome);
      break;
    }
    case 'storage_tank': {
      const body = new THREE.Mesh(new THREE.CylinderGeometry(2, 2, 3.2, 24), bodyMaterial);
      body.position.y = 1.6;
      body.castShadow = true;
      group.add(body);
      const cap = new THREE.Mesh(new THREE.ConeGeometry(2, 0.8, 24), bodyMaterial);
      cap.position.y = 3.6;
      group.add(cap);
      break;
    }
    case 'valve': {
      const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 1.4, 12), bodyMaterial);
      stem.position.y = 0.7;
      group.add(stem);
      const wheel = new THREE.Mesh(new THREE.TorusGeometry(0.45, 0.08, 8, 16), new THREE.MeshStandardMaterial({ color: '#9AA4B2' }));
      wheel.position.y = 1.5;
      wheel.rotation.x = Math.PI / 2;
      group.add(wheel);
      spinner = wheel;
      break;
    }
    case 'conveyor_motor': {
      const housing = new THREE.Mesh(new THREE.BoxGeometry(1.6, 1.2, 1.2), bodyMaterial);
      housing.position.y = 0.6;
      housing.castShadow = true;
      group.add(housing);
      const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.15, 1.8, 10), new THREE.MeshStandardMaterial({ color: '#9AA4B2' }));
      shaft.rotation.z = Math.PI / 2;
      shaft.position.set(1.4, 0.6, 0);
      group.add(shaft);
      spinner = shaft;
      break;
    }
    case 'pump': {
      const housing = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1, 1.4), bodyMaterial);
      housing.position.y = 0.5;
      housing.castShadow = true;
      group.add(housing);
      const impellerHousing = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 0.6, 16), bodyMaterial);
      impellerHousing.rotation.z = Math.PI / 2;
      impellerHousing.position.set(0.9, 0.5, 0);
      group.add(impellerHousing);
      spinner = impellerHousing;
      break;
    }
    default: {
      const box = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.2, 1.2), bodyMaterial);
      box.position.y = 0.6;
      group.add(box);
    }
  }

  return { group, spinner, bodyMaterial };
}

export function buildMachines(world: WorldTopology): MachineRefs {
  const group = new THREE.Group();
  group.name = 'machines';
  const byId = new Map<string, MachineEntry>();

  for (const zone of world.zones) {
    zone.equipment.forEach((eq, index) => {
      const pos2d = equipmentPosition(zone.zone_id, index, zone.equipment.length);
      const { group: machineGroup, spinner, bodyMaterial } = buildMachineGeometry(eq.machine_class);
      machineGroup.position.set(toWorldX(pos2d.x), 0, toWorldZ(pos2d.y));
      machineGroup.userData.mapObjectKind = 'machine';
      machineGroup.userData.mapObjectId = eq.equipment_id;
      machineGroup.traverse((child) => {
        child.userData.mapObjectKind = 'machine';
        child.userData.mapObjectId = eq.equipment_id;
      });

      const label = createTextSprite(eq.tag, { fontSize: 34 });
      label.position.set(0, 3.4, 0);
      machineGroup.add(label);

      group.add(machineGroup);
      byId.set(eq.equipment_id, { group: machineGroup, spinner, bodyMaterial, label });
    });
  }

  return { group, byId };
}

export function updateMachines(refs: MachineRefs, zones: ZoneSnapshot[], deltaSeconds: number) {
  for (const zone of zones) {
    for (const eq of zone.equipment) {
      const entry = refs.byId.get(eq.equipment_id);
      if (!entry) continue;

      const severity = fromSimulatorSeverity(eq.severity);
      const color = new THREE.Color(SEVERITY_HEX[severity]);
      entry.bodyMaterial.emissive = color;
      entry.bodyMaterial.emissiveIntensity = severity === 'nominal' ? 0.08 : 0.35;

      if (entry.spinner && eq.status === 'operational') {
        const rpm = eq.readings.rpm ?? 0;
        const speed = rpm > 0 ? Math.min(rpm / 300, 12) : 4; // valves/pumps without an RPM reading still get a gentle idle spin
        entry.spinner.rotation.x += speed * deltaSeconds;
      }
    }
  }
}
