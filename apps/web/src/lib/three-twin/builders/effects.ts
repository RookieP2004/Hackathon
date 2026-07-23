import * as THREE from 'three';
import { cameraPosition, gasSensorPosition } from '@/lib/factory-map-layout';
import { toWorldX, toWorldZ, zoneWorldRect } from '@/lib/three-twin/coordinates';
import { SEVERITY_HEX } from '@/lib/three-twin/severity-colors';
import { fromSimulatorSeverity } from '@/components/dashboard/severity';
import type { WorldTopology, ZoneSnapshot } from '@/lib/services/simulator';

const SMOKE_PARTICLES_PER_ZONE = 60;
const SMOKE_RISE_HEIGHT = 9;

interface GasCloudEntry {
  mesh: THREE.Mesh;
  material: THREE.MeshStandardMaterial;
}

interface SmokeEntry {
  points: THREE.Points;
  material: THREE.PointsMaterial;
  velocities: Float32Array;
  origin: THREE.Vector3;
}

interface FireEntry {
  group: THREE.Group;
  cone: THREE.Mesh;
  light: THREE.PointLight;
}

interface BeaconEntry {
  mesh: THREE.Mesh;
  material: THREE.MeshStandardMaterial;
}

export interface EffectsRefs {
  group: THREE.Group;
  gasClouds: Map<string, GasCloudEntry>;
  smoke: Map<string, SmokeEntry>;
  fire: Map<string, FireEntry>;
  gasSensorBeacons: Map<string, BeaconEntry>;
  cameraBeacons: Map<string, BeaconEntry>;
}

export function buildEffects(world: WorldTopology): EffectsRefs {
  const group = new THREE.Group();
  group.name = 'effects';
  const gasClouds = new Map<string, GasCloudEntry>();
  const smoke = new Map<string, SmokeEntry>();
  const fire = new Map<string, FireEntry>();
  const gasSensorBeacons = new Map<string, BeaconEntry>();
  const cameraBeacons = new Map<string, BeaconEntry>();

  for (const zone of world.zones) {
    const rect = zoneWorldRect(zone.zone_id);

    // Gas cloud — a soft glowing blob, invisible at baseline, fattening and
    // brightening as concentration rises.
    const cloudGeometry = new THREE.SphereGeometry(1, 16, 12);
    const cloudMaterial = new THREE.MeshStandardMaterial({
      color: '#E8C547',
      transparent: true,
      opacity: 0,
      depthWrite: false,
      emissive: '#E8C547',
      emissiveIntensity: 0.2,
    });
    const cloudMesh = new THREE.Mesh(cloudGeometry, cloudMaterial);
    cloudMesh.position.set(rect.centerX, 2.5, rect.centerZ);
    group.add(cloudMesh);
    gasClouds.set(zone.zone_id, { mesh: cloudMesh, material: cloudMaterial });

    // Smoke — a fixed-size particle pool per zone, recycled every frame
    // (positions reset to ground level once they rise past SMOKE_RISE_HEIGHT)
    // rather than allocated dynamically, so this stays cheap regardless of
    // how long a fire burns.
    const positions = new Float32Array(SMOKE_PARTICLES_PER_ZONE * 3);
    const velocities = new Float32Array(SMOKE_PARTICLES_PER_ZONE);
    for (let i = 0; i < SMOKE_PARTICLES_PER_ZONE; i++) {
      positions[i * 3] = rect.centerX + (Math.random() - 0.5) * rect.width * 0.6;
      positions[i * 3 + 1] = Math.random() * SMOKE_RISE_HEIGHT;
      positions[i * 3 + 2] = rect.centerZ + (Math.random() - 0.5) * rect.depth * 0.6;
      velocities[i] = 0.6 + Math.random() * 0.8;
    }
    const smokeGeometry = new THREE.BufferGeometry();
    smokeGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const smokeMaterial = new THREE.PointsMaterial({
      color: '#9AA4B2',
      size: 1.4,
      transparent: true,
      opacity: 0,
      depthWrite: false,
    });
    const points = new THREE.Points(smokeGeometry, smokeMaterial);
    group.add(points);
    smoke.set(zone.zone_id, { points, material: smokeMaterial, velocities, origin: new THREE.Vector3(rect.centerX, 0, rect.centerZ) });

    // Fire — a flickering emissive cone + a warm point light, hidden until an
    // active fire/explosion scenario reaches this zone.
    const fireGroup = new THREE.Group();
    const coneMaterial = new THREE.MeshStandardMaterial({ color: '#F5A524', emissive: '#E5484D', emissiveIntensity: 1.5 });
    const cone = new THREE.Mesh(new THREE.ConeGeometry(1.1, 2.4, 12), coneMaterial);
    cone.position.y = 1.2;
    fireGroup.add(cone);
    const fireLight = new THREE.PointLight('#F5A524', 0, 18, 2);
    fireLight.position.y = 2;
    fireGroup.add(fireLight);
    fireGroup.position.set(rect.centerX, 0, rect.centerZ);
    fireGroup.visible = false;
    group.add(fireGroup);
    fire.set(zone.zone_id, { group: fireGroup, cone, light: fireLight });

    // Sensor beacons — small pulsing markers at the same spots the 2D map uses.
    const gasPos = gasSensorPosition(zone.zone_id);
    const gasBeaconMaterial = new THREE.MeshStandardMaterial({ color: SEVERITY_HEX.nominal, emissive: SEVERITY_HEX.nominal, emissiveIntensity: 0.6 });
    const gasBeacon = new THREE.Mesh(new THREE.SphereGeometry(0.22, 12, 10), gasBeaconMaterial);
    gasBeacon.position.set(toWorldX(gasPos.x), 1.6, toWorldZ(gasPos.y));
    gasBeacon.userData.mapObjectKind = 'gasSensor';
    gasBeacon.userData.mapObjectId = zone.zone_id;
    group.add(gasBeacon);
    gasSensorBeacons.set(zone.zone_id, { mesh: gasBeacon, material: gasBeaconMaterial });

    const camPos = cameraPosition(zone.zone_id);
    const camBeaconMaterial = new THREE.MeshStandardMaterial({ color: '#4F5FE8', emissive: '#4F5FE8', emissiveIntensity: 0.5 });
    const camBeacon = new THREE.Mesh(new THREE.ConeGeometry(0.2, 0.4, 8), camBeaconMaterial);
    camBeacon.position.set(toWorldX(camPos.x), 2.2, toWorldZ(camPos.y));
    camBeacon.rotation.x = Math.PI;
    camBeacon.userData.mapObjectKind = 'camera';
    camBeacon.userData.mapObjectId = zone.zone_id;
    group.add(camBeacon);
    cameraBeacons.set(zone.zone_id, { mesh: camBeacon, material: camBeaconMaterial });
  }

  return { group, gasClouds, smoke, fire, gasSensorBeacons, cameraBeacons };
}

export function updateEffects(refs: EffectsRefs, zones: ZoneSnapshot[], elapsedSeconds: number, deltaSeconds: number) {
  for (const zone of zones) {
    const gasPct = zone.ambient.gas_pct_lel;
    const gasCloud = refs.gasClouds.get(zone.zone_id);
    if (gasCloud) {
      const visible = gasPct > 5;
      const scale = 1 + Math.min(gasPct / 15, 4);
      gasCloud.mesh.scale.setScalar(THREE.MathUtils.lerp(gasCloud.mesh.scale.x, scale, 0.05));
      gasCloud.material.opacity = THREE.MathUtils.lerp(gasCloud.material.opacity, visible ? Math.min(gasPct / 60, 0.55) : 0, 0.05);
      gasCloud.mesh.rotation.y += deltaSeconds * 0.1;
    }

    const smoke = refs.smoke.get(zone.zone_id);
    if (smoke) {
      const smokePct = zone.ambient.smoke_pct_obscuration;
      smoke.material.opacity = THREE.MathUtils.lerp(smoke.material.opacity, Math.min(smokePct / 100, 0.85), 0.05);
      const positions = smoke.points.geometry.getAttribute('position') as THREE.BufferAttribute;
      for (let i = 0; i < SMOKE_PARTICLES_PER_ZONE; i++) {
        const y = positions.getY(i) + (smoke.velocities[i] ?? 0.6) * deltaSeconds;
        if (y > SMOKE_RISE_HEIGHT) {
          positions.setY(i, 0);
        } else {
          positions.setY(i, y);
        }
      }
      positions.needsUpdate = true;
    }

    const fire = refs.fire.get(zone.zone_id);
    if (fire) {
      const active = zone.severity === 'critical' && (zone.ambient.temperature_c > 60 || zone.ambient.smoke_pct_obscuration > 50);
      fire.group.visible = active;
      if (active) {
        const flicker = 1.2 + Math.sin(elapsedSeconds * 14) * 0.3 + Math.random() * 0.2;
        (fire.cone.material as THREE.MeshStandardMaterial).emissiveIntensity = flicker;
        fire.light.intensity = flicker * 3;
        fire.cone.scale.y = 1 + Math.sin(elapsedSeconds * 20) * 0.08;
      }
    }

    const gasBeacon = refs.gasSensorBeacons.get(zone.zone_id);
    if (gasBeacon) {
      const color = SEVERITY_HEX[fromSimulatorSeverity(zone.ambient_severity)];
      gasBeacon.material.color.set(color);
      gasBeacon.material.emissive.set(color);
      gasBeacon.material.emissiveIntensity = 0.4 + Math.abs(Math.sin(elapsedSeconds * 3)) * 0.4;
    }

    const camBeacon = refs.cameraBeacons.get(zone.zone_id);
    if (camBeacon) {
      const alarmed = zone.camera.event_type !== 'normal';
      const color = alarmed ? SEVERITY_HEX.critical : '#4F5FE8';
      camBeacon.material.color.set(color);
      camBeacon.material.emissive.set(color);
      camBeacon.material.emissiveIntensity = alarmed ? 0.5 + Math.abs(Math.sin(elapsedSeconds * 8)) * 0.5 : 0.5;
    }
  }
}
