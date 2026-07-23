import type { Edge, Node } from 'reactflow';
import { fromSimulatorSeverity } from '@/components/dashboard/severity';
import type {
  BuildingNodeData,
  CameraNodeData,
  EmergencyResponderNodeData,
  ExitNodeData,
  FireSystemNodeData,
  GasSensorNodeData,
  MachineNodeData,
  RobotNodeData,
  VehicleNodeData,
  WorkerNodeData,
  ZoneNodeData,
} from '@/components/factory-map/types';
import type { PipelineEdgeData } from '@/components/factory-map/pipeline-edge';
import {
  BUILDING_LAYOUT,
  cameraPosition,
  equipmentPosition,
  exitPosition,
  fireSystemPosition,
  gasSensorPosition,
  indexOffset,
  mobileBasePosition,
  zoneRect,
} from '@/lib/factory-map-layout';
import { offsetFromAnchor, type AnchorRegistry } from '@/lib/mobile-position';
import type { TelemetrySnapshot } from '@/lib/services/simulator';

function groupByZone<T extends { zone_id: string }>(items: T[]): Map<string, T[]> {
  const map = new Map<string, T[]>();
  for (const item of items) {
    const list = map.get(item.zone_id) ?? [];
    list.push(item);
    map.set(item.zone_id, list);
  }
  return map;
}

export function buildMapGraph(
  snapshot: TelemetrySnapshot,
  anchors: AnchorRegistry,
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];

  for (const building of snapshot.buildings) {
    const rect = BUILDING_LAYOUT[building.building_id] ?? { x: 0, y: 0, width: 400, height: 300 };
    const data: BuildingNodeData = {
      kind: 'building',
      id: building.building_id,
      label: building.name,
      severity: fromSimulatorSeverity(building.severity),
      statusText: building.severity,
      width: rect.width,
      height: rect.height,
    };
    nodes.push({
      id: `building:${building.building_id}`,
      type: 'building',
      position: { x: rect.x, y: rect.y },
      data,
      draggable: false,
      selectable: false,
      zIndex: 0,
    });
  }

  for (const zone of snapshot.zones) {
    const rect = zoneRect(zone.zone_id);
    const data: ZoneNodeData = {
      kind: 'zone',
      id: zone.zone_id,
      label: zone.name,
      severity: fromSimulatorSeverity(zone.severity),
      statusText: zone.mode,
      width: rect.width,
      height: rect.height,
    };
    nodes.push({
      id: `zone:${zone.zone_id}`,
      type: 'zone',
      position: { x: rect.x, y: rect.y },
      data,
      draggable: false,
      zIndex: 1,
    });

    zone.equipment.forEach((eq, index) => {
      const pos = equipmentPosition(zone.zone_id, index, zone.equipment.length);
      const data: MachineNodeData = {
        kind: 'machine',
        id: eq.equipment_id,
        label: eq.tag,
        severity: fromSimulatorSeverity(eq.severity),
        statusText: eq.status,
        machineClass: eq.machine_class,
      };
      nodes.push({ id: `machine:${eq.equipment_id}`, type: 'machine', position: pos, data, draggable: false, zIndex: 3 });
    });

    const gasPos = gasSensorPosition(zone.zone_id);
    const gasData: GasSensorNodeData = {
      kind: 'gasSensor',
      id: zone.zone_id,
      label: 'Gas Sensor',
      severity: fromSimulatorSeverity(zone.ambient_severity),
      statusText: zone.ambient_severity,
      value: zone.ambient.gas_pct_lel,
    };
    nodes.push({ id: `gasSensor:${zone.zone_id}`, type: 'gasSensor', position: gasPos, data: gasData, draggable: false, zIndex: 3 });

    const camPos = cameraPosition(zone.zone_id);
    const camData: CameraNodeData = {
      kind: 'camera',
      id: zone.zone_id,
      label: 'Camera',
      severity:
        zone.camera.event_type === 'normal'
          ? 'nominal'
          : ['fire_detected', 'explosion_detected', 'person_down'].includes(zone.camera.event_type)
            ? 'critical'
            : 'medium',
      statusText: zone.camera.event_type,
      eventType: zone.camera.event_type,
    };
    nodes.push({ id: `camera:${zone.zone_id}`, type: 'camera', position: camPos, data: camData, draggable: false, zIndex: 3 });
  }

  const exitsByZone = groupByZone(snapshot.emergency_exits);
  for (const [zoneId, exits] of exitsByZone) {
    exits.forEach((ex, index) => {
      const pos = exitPosition(zoneId, index, exits.length);
      const data: ExitNodeData = {
        kind: 'exit',
        id: ex.exit_id,
        label: ex.name.split(' ').slice(-2).join(' '),
        severity: ex.status === 'blocked' ? 'critical' : 'nominal',
        statusText: ex.status,
      };
      nodes.push({ id: `exit:${ex.exit_id}`, type: 'exit', position: pos, data, draggable: false, zIndex: 3 });
    });
  }

  for (const fs of snapshot.fire_systems) {
    const pos = fireSystemPosition(fs.zone_id);
    const data: FireSystemNodeData = {
      kind: 'fireSystem',
      id: fs.fire_system_id,
      label: fs.system_type,
      severity: fs.status === 'fault' ? 'critical' : fs.status === 'discharged' ? 'high' : 'nominal',
      statusText: fs.status,
    };
    nodes.push({ id: `fireSystem:${fs.fire_system_id}`, type: 'fireSystem', position: pos, data, draggable: false, zIndex: 3 });
  }

  const workersByZone = groupByZone(snapshot.workers);
  for (const [zoneId, workers] of workersByZone) {
    const base = mobileBasePosition(zoneId);
    workers.forEach((w, index) => {
      const spread = indexOffset(index);
      const { dx, dy } = offsetFromAnchor(anchors, `worker:${w.worker_id}`, w.gps.lat, w.gps.lon);
      const data: WorkerNodeData = {
        kind: 'worker',
        id: w.worker_id,
        label: w.name.split(' ')[0] ?? w.name,
        severity: fromSimulatorSeverity(w.severity),
        statusText: w.status,
        collapsed: w.status === 'collapsed',
      };
      nodes.push({
        id: `worker:${w.worker_id}`,
        type: 'worker',
        position: { x: base.x + spread.x + dx, y: base.y + spread.y + dy },
        data,
        draggable: false,
        zIndex: 4,
      });
    });
  }

  const vehiclesByZone = groupByZone(snapshot.vehicles);
  for (const [zoneId, vehicles] of vehiclesByZone) {
    const base = mobileBasePosition(zoneId);
    vehicles.forEach((v, index) => {
      const spread = indexOffset(index + 3); // offset from workers' golden-angle sequence so icons don't overlap
      const { dx, dy } = offsetFromAnchor(anchors, `vehicle:${v.vehicle_id}`, v.gps.lat, v.gps.lon);
      const data: VehicleNodeData = {
        kind: 'vehicle',
        id: v.vehicle_id,
        label: v.name,
        severity: 'nominal',
        statusText: v.status,
        vehicleType: v.vehicle_type,
      };
      nodes.push({
        id: `vehicle:${v.vehicle_id}`,
        type: 'vehicle',
        position: { x: base.x + spread.x + dx, y: base.y + spread.y + dy },
        data,
        draggable: false,
        zIndex: 4,
      });
    });
  }

  // Arm robots are bolted to one piece of equipment -- park them just beside it.
  const equipmentPositionById = new Map<string, { x: number; y: number }>();
  for (const zone of snapshot.zones) {
    zone.equipment.forEach((eq, index) => {
      equipmentPositionById.set(eq.equipment_id, equipmentPosition(zone.zone_id, index, zone.equipment.length));
    });
  }

  const amrRobotsByZone = groupByZone(snapshot.robots.filter((r) => r.robot_type === 'amr'));
  for (const [zoneId, robots] of amrRobotsByZone) {
    const base = mobileBasePosition(zoneId);
    robots.forEach((r, index) => {
      const spread = indexOffset(index + 6); // past workers' (0..) and vehicles' (3..) golden-angle ranges
      const { dx, dy } = offsetFromAnchor(anchors, `robot:${r.robot_id}`, r.gps.lat, r.gps.lon);
      const data: RobotNodeData = {
        kind: 'robot',
        id: r.robot_id,
        label: r.name,
        severity: fromSimulatorSeverity('normal'),
        statusText: r.status,
        robotType: r.robot_type,
      };
      nodes.push({
        id: `robot:${r.robot_id}`,
        type: 'robot',
        position: { x: base.x + spread.x + dx, y: base.y + spread.y + dy },
        data,
        draggable: false,
        zIndex: 4,
      });
    });
  }

  for (const r of snapshot.robots.filter((robot) => robot.robot_type === 'arm')) {
    const anchor = r.equipment_id ? equipmentPositionById.get(r.equipment_id) : undefined;
    const pos = anchor ? { x: anchor.x + 50, y: anchor.y } : mobileBasePosition(r.zone_id);
    const data: RobotNodeData = {
      kind: 'robot',
      id: r.robot_id,
      label: r.name,
      severity: r.status === 'fault' ? 'critical' : 'nominal',
      statusText: r.status,
      robotType: r.robot_type,
    };
    nodes.push({ id: `robot:${r.robot_id}`, type: 'robot', position: pos, data, draggable: false, zIndex: 4 });
  }

  // Emergency responders travel between zones in reality (see engine.py's
  // goal-directed lerp), but this 2D schematic's zones are disjoint rectangles
  // with no "between zones" space to place them in mid-transit -- so here they
  // stay pinned at their home/muster zone, with status (standby/responding/
  // on_scene) conveyed through the label and pulse instead of literal travel.
  // The 3D Digital Twin (a continuous world) is where responders actually move.
  const respondersByHomeZone = groupByZone(
    snapshot.emergency_responders.map((r) => ({ ...r, zone_id: r.home_zone_id })),
  );
  for (const [zoneId, responders] of respondersByHomeZone) {
    const base = mobileBasePosition(zoneId);
    responders.forEach((r, index) => {
      const spread = indexOffset(index + 9);
      const data: EmergencyResponderNodeData = {
        kind: 'emergencyResponder',
        id: r.responder_id,
        label: `${r.name.split(' ').slice(-1)[0]} (${r.status})`,
        severity: r.status === 'standby' ? 'nominal' : 'high',
        statusText: r.status,
      };
      nodes.push({
        id: `emergencyResponder:${r.responder_id}`,
        type: 'emergencyResponder',
        position: { x: base.x + spread.x, y: base.y + spread.y },
        data,
        draggable: false,
        zIndex: 4,
      });
    });
  }

  const edges: Edge[] = snapshot.pipelines.map((pipe) => ({
    id: `pipeline:${pipe.pipeline_id}`,
    source: `machine:${pipe.from_equipment_id}`,
    sourceHandle: 'source',
    target: `machine:${pipe.to_equipment_id}`,
    targetHandle: 'target',
    type: 'pipeline',
    data: {
      pipelineId: pipe.pipeline_id,
      label: pipe.name,
      status: pipe.status,
      severity: fromSimulatorSeverity(pipe.severity),
    } satisfies PipelineEdgeData,
    zIndex: 2,
  }));

  return { nodes, edges };
}
