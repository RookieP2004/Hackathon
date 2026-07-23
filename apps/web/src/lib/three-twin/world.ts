import * as THREE from 'three';
import type { DigitalTwinScene } from './scene';
import { buildEnvironment, updateEnvironment, type EnvironmentRefs } from './builders/environment';
import { buildMachines, updateMachines, type MachineRefs } from './builders/machines';
import { buildPipelines, updatePipelines, type PipelineRefs } from './builders/pipelines';
import { buildMobileAgents, updateMobileAgents, type MobileAgentRefs } from './builders/mobile-agents';
import { buildEffects, updateEffects, type EffectsRefs } from './builders/effects';
import { buildSafetyEquipment, updateSafetyEquipment, type SafetyEquipmentRefs } from './builders/safety-equipment';
import { buildPredictionOverlay, updatePredictionOverlay, type PredictionOverlayRefs } from './builders/prediction-overlay';
import { computeZoneTrendProjections } from './prediction';
import { computeSceneBounds } from './coordinates';
import { createAnchorRegistry } from '@/lib/mobile-position';
import type { TelemetrySnapshot, WorldTopology } from '@/lib/services/simulator';

/**
 * Owns every 3D object in the twin and knows how to refresh them from a live
 * (or scrubbed-historical) snapshot. Built once from the static WorldTopology
 * (positions/geometry never change), then `update()` is called every tick
 * with whichever snapshot should currently be displayed.
 */
export class DigitalTwinWorld {
  private environment: EnvironmentRefs;
  private machines: MachineRefs;
  private pipelines: PipelineRefs;
  private mobileAgents: MobileAgentRefs;
  private effects: EffectsRefs;
  private safetyEquipment: SafetyEquipmentRefs;
  private predictionOverlay: PredictionOverlayRefs;
  private anchors = createAnchorRegistry();
  private elapsedSeconds = 0;
  showPredictionOverlay = false;

  constructor(
    private scene: DigitalTwinScene,
    world: WorldTopology,
  ) {
    this.environment = buildEnvironment(world);
    this.machines = buildMachines(world);
    this.pipelines = buildPipelines(world);
    this.mobileAgents = buildMobileAgents(world);
    this.effects = buildEffects(world);
    this.safetyEquipment = buildSafetyEquipment(world);
    this.predictionOverlay = buildPredictionOverlay(world);

    scene.scene.add(
      this.environment.group,
      this.machines.group,
      this.pipelines.group,
      this.mobileAgents.group,
      this.effects.group,
      this.safetyEquipment.group,
      this.predictionOverlay.group,
    );

    const bounds = computeSceneBounds(world.buildings.map((b) => b.building_id));
    scene.orbitControls.target.set(bounds.centerX, 2, bounds.centerZ);
    scene.camera.position.set(bounds.centerX - bounds.radius * 0.3, bounds.radius * 0.9, bounds.centerZ + bounds.radius * 1.1);
    scene.orbitControls.maxDistance = bounds.radius * 6;
    scene.orbitControls.update();
  }

  setPredictionOverlayVisible(visible: boolean) {
    this.showPredictionOverlay = visible;
    this.predictionOverlay.group.visible = visible;
  }

  /** Called once per animation frame; `snapshot` is the tick currently being displayed (live or scrubbed) and may repeat while playback is paused. */
  update(snapshot: TelemetrySnapshot, history: TelemetrySnapshot[], deltaSeconds: number) {
    this.elapsedSeconds += deltaSeconds;

    const zoneSeverities = new Map(snapshot.zones.map((z) => [z.zone_id, z.severity]));
    updateEnvironment(this.environment, zoneSeverities);
    updateMachines(this.machines, snapshot.zones, deltaSeconds);
    updatePipelines(this.pipelines, snapshot.pipelines, deltaSeconds);
    updateMobileAgents(this.mobileAgents, snapshot, this.anchors, deltaSeconds);
    updateEffects(this.effects, snapshot.zones, this.elapsedSeconds, deltaSeconds);
    updateSafetyEquipment(this.safetyEquipment, snapshot.emergency_exits, snapshot.fire_systems, this.elapsedSeconds);

    if (this.showPredictionOverlay) {
      const projections = computeZoneTrendProjections(history);
      updatePredictionOverlay(this.predictionOverlay, projections, this.elapsedSeconds);
    }
  }

  dispose() {
    for (const group of [
      this.environment.group,
      this.machines.group,
      this.pipelines.group,
      this.mobileAgents.group,
      this.effects.group,
      this.safetyEquipment.group,
      this.predictionOverlay.group,
    ]) {
      this.scene.scene.remove(group);
      group.traverse((obj) => {
        if (obj instanceof THREE.Mesh || obj instanceof THREE.Points) {
          obj.geometry?.dispose();
          const materials = Array.isArray(obj.material) ? obj.material : [obj.material];
          materials.forEach((m) => m?.dispose());
        }
        if (obj instanceof THREE.Sprite) {
          obj.material.map?.dispose();
          obj.material.dispose();
        }
      });
    }
  }
}
