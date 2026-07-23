import type { DashboardSeverity } from '@/components/dashboard/severity';

export type MapObjectKind =
  | 'building'
  | 'zone'
  | 'machine'
  | 'worker'
  | 'vehicle'
  | 'exit'
  | 'fireSystem'
  | 'gasSensor'
  | 'camera'
  | 'pipeline'
  | 'robot'
  | 'emergencyResponder';

export interface BaseMapNodeData {
  kind: MapObjectKind;
  id: string;
  label: string;
  severity: DashboardSeverity;
  statusText: string;
}

export interface BuildingNodeData extends BaseMapNodeData {
  kind: 'building';
  width: number;
  height: number;
}

export interface ZoneNodeData extends BaseMapNodeData {
  kind: 'zone';
  width: number;
  height: number;
}

export interface MachineNodeData extends BaseMapNodeData {
  kind: 'machine';
  machineClass: string;
}

export interface WorkerNodeData extends BaseMapNodeData {
  kind: 'worker';
  collapsed: boolean;
}

export interface VehicleNodeData extends BaseMapNodeData {
  kind: 'vehicle';
  vehicleType: string;
}

export interface ExitNodeData extends BaseMapNodeData {
  kind: 'exit';
}

export interface FireSystemNodeData extends BaseMapNodeData {
  kind: 'fireSystem';
}

export interface GasSensorNodeData extends BaseMapNodeData {
  kind: 'gasSensor';
  value: number;
}

export interface CameraNodeData extends BaseMapNodeData {
  kind: 'camera';
  eventType: string;
}

export interface RobotNodeData extends BaseMapNodeData {
  kind: 'robot';
  robotType: string;
}

export interface EmergencyResponderNodeData extends BaseMapNodeData {
  kind: 'emergencyResponder';
}

export type MapNodeData =
  | BuildingNodeData
  | ZoneNodeData
  | MachineNodeData
  | WorkerNodeData
  | VehicleNodeData
  | ExitNodeData
  | FireSystemNodeData
  | GasSensorNodeData
  | CameraNodeData
  | RobotNodeData
  | EmergencyResponderNodeData;
