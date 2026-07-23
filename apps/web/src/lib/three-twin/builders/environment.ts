import * as THREE from 'three';
import { buildingWorldRect, zoneWorldRect } from '@/lib/three-twin/coordinates';
import { createTextSprite } from '@/lib/three-twin/text-sprite';
import { SEVERITY_HEX } from '@/lib/three-twin/severity-colors';
import { fromSimulatorSeverity } from '@/components/dashboard/severity';
import type { WorldTopology } from '@/lib/services/simulator';

const BUILDING_POST_HEIGHT = 6;
const BUILDING_COLOR = '#252A31';

export interface EnvironmentRefs {
  group: THREE.Group;
  zoneFloors: Map<string, THREE.MeshStandardMaterial>;
}

/** Buildings/zones are static in this demo world, so their geometry is built
 * once from the topology; only floor color (severity) changes per tick. Low
 * open perimeters (posts, no solid walls/roof) are deliberate — the whole
 * point of a walk-through twin is seeing everything, not a house you can't
 * see inside. */
export function buildEnvironment(world: WorldTopology): EnvironmentRefs {
  const group = new THREE.Group();
  group.name = 'environment';
  const zoneFloors = new Map<string, THREE.MeshStandardMaterial>();

  for (const building of world.buildings) {
    const rect = buildingWorldRect(building.building_id);
    const postGeometry = new THREE.CylinderGeometry(0.15, 0.15, BUILDING_POST_HEIGHT, 8);
    const postMaterial = new THREE.MeshStandardMaterial({ color: BUILDING_COLOR });
    const corners: Array<[number, number]> = [
      [rect.x, rect.z],
      [rect.x + rect.width, rect.z],
      [rect.x, rect.z + rect.depth],
      [rect.x + rect.width, rect.z + rect.depth],
    ];
    for (const [x, z] of corners) {
      const post = new THREE.Mesh(postGeometry, postMaterial);
      post.position.set(x, BUILDING_POST_HEIGHT / 2, z);
      post.castShadow = true;
      group.add(post);
    }

    // A slim beam tracing the building's footprint at roof height, enough to
    // read as "a building" from a distance without blocking the interior view.
    const outline = new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(rect.x, BUILDING_POST_HEIGHT, rect.z),
        new THREE.Vector3(rect.x + rect.width, BUILDING_POST_HEIGHT, rect.z),
        new THREE.Vector3(rect.x + rect.width, BUILDING_POST_HEIGHT, rect.z + rect.depth),
        new THREE.Vector3(rect.x, BUILDING_POST_HEIGHT, rect.z + rect.depth),
      ]),
      new THREE.LineBasicMaterial({ color: BUILDING_COLOR }),
    );
    group.add(outline);

    const label = createTextSprite(building.name.toUpperCase(), { color: '#5B6472', fontSize: 32, scale: 1.4 });
    label.position.set(rect.x + 1.5, BUILDING_POST_HEIGHT + 1.2, rect.z + 1.5);
    group.add(label);
  }

  for (const zone of world.zones) {
    const rect = zoneWorldRect(zone.zone_id);
    const floorGeometry = new THREE.PlaneGeometry(rect.width - 0.4, rect.depth - 0.4);
    const floorMaterial = new THREE.MeshStandardMaterial({
      color: SEVERITY_HEX.nominal,
      transparent: true,
      opacity: 0.16,
      roughness: 1,
    });
    const floor = new THREE.Mesh(floorGeometry, floorMaterial);
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(rect.centerX, 0.02, rect.centerZ);
    floor.receiveShadow = true;
    floor.userData.mapObjectKind = 'zone';
    floor.userData.mapObjectId = zone.zone_id;
    group.add(floor);
    zoneFloors.set(zone.zone_id, floorMaterial);

    const border = new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(rect.x, 0.03, rect.z),
        new THREE.Vector3(rect.x + rect.width, 0.03, rect.z),
        new THREE.Vector3(rect.x + rect.width, 0.03, rect.z + rect.depth),
        new THREE.Vector3(rect.x, 0.03, rect.z + rect.depth),
      ]),
      new THREE.LineBasicMaterial({ color: '#4F5FE8', transparent: true, opacity: 0.5 }),
    );
    group.add(border);

    const label = createTextSprite(zone.name, { color: '#F2F4F7', fontSize: 40 });
    label.position.set(rect.centerX, 3.2, rect.z + 0.8);
    group.add(label);
  }

  return { group, zoneFloors };
}

export function updateEnvironment(refs: EnvironmentRefs, zoneSeverities: Map<string, string>) {
  for (const [zoneId, material] of refs.zoneFloors) {
    const severity = zoneSeverities.get(zoneId);
    if (!severity) continue;
    material.color.set(SEVERITY_HEX[fromSimulatorSeverity(severity as 'normal' | 'warning' | 'critical')]);
  }
}
