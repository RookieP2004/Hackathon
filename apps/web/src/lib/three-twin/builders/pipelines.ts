import * as THREE from 'three';
import { equipmentPosition } from '@/lib/factory-map-layout';
import { toWorldX, toWorldZ } from '@/lib/three-twin/coordinates';
import { SEVERITY_HEX } from '@/lib/three-twin/severity-colors';
import { fromSimulatorSeverity } from '@/components/dashboard/severity';
import type { PipelineSnapshot, WorldTopology } from '@/lib/services/simulator';

const PIPE_HEIGHT = 2.6;
const PIPE_RADIUS = 0.16;

function stripeTexture(): THREE.Texture {
  const canvas = document.createElement('canvas');
  canvas.width = 64;
  canvas.height = 8;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#00000000';
  ctx.clearRect(0, 0, 64, 8);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 20, 8);
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(6, 1);
  return texture;
}

interface PipelineEntry {
  material: THREE.MeshStandardMaterial;
  texture: THREE.Texture;
}

export interface PipelineRefs {
  group: THREE.Group;
  byId: Map<string, PipelineEntry>;
}

export function buildPipelines(world: WorldTopology): PipelineRefs {
  const group = new THREE.Group();
  group.name = 'pipelines';
  const byId = new Map<string, PipelineEntry>();

  const equipmentPositionById = new Map<string, THREE.Vector3>();
  for (const zone of world.zones) {
    zone.equipment.forEach((eq, index) => {
      const pos2d = equipmentPosition(zone.zone_id, index, zone.equipment.length);
      equipmentPositionById.set(eq.equipment_id, new THREE.Vector3(toWorldX(pos2d.x), PIPE_HEIGHT, toWorldZ(pos2d.y)));
    });
  }

  for (const pipe of world.pipelines) {
    const from = equipmentPositionById.get(pipe.from_equipment_id);
    const to = equipmentPositionById.get(pipe.to_equipment_id);
    if (!from || !to) continue;

    const mid = from.clone().add(to).multiplyScalar(0.5);
    mid.y += 1.5 + from.distanceTo(to) * 0.05; // a gentle arc, more pronounced over longer runs (cross-building lines)
    const curve = new THREE.CatmullRomCurve3([from, mid, to]);
    const geometry = new THREE.TubeGeometry(curve, 32, PIPE_RADIUS, 8, false);
    const texture = stripeTexture();
    const material = new THREE.MeshStandardMaterial({
      color: SEVERITY_HEX.nominal,
      emissive: SEVERITY_HEX.nominal,
      emissiveMap: texture,
      emissiveIntensity: 0.9,
      roughness: 0.6,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.userData.mapObjectKind = 'pipeline';
    mesh.userData.mapObjectId = pipe.pipeline_id;
    mesh.castShadow = true;
    group.add(mesh);
    byId.set(pipe.pipeline_id, { material, texture });
  }

  return { group, byId };
}

export function updatePipelines(refs: PipelineRefs, pipelines: PipelineSnapshot[], deltaSeconds: number) {
  for (const pipe of pipelines) {
    const entry = refs.byId.get(pipe.pipeline_id);
    if (!entry) continue;
    const flowing = pipe.status === 'flowing';
    const color = flowing ? SEVERITY_HEX[fromSimulatorSeverity(pipe.severity)] : '#5B6472';
    entry.material.color.set(color);
    entry.material.emissive.set(color);
    entry.material.emissiveIntensity = flowing ? 0.9 : 0.15;
    if (flowing) {
      entry.texture.offset.x -= deltaSeconds * 0.6;
    }
  }
}
