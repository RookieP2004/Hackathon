import type { NodeProps } from 'reactflow';
import { Bot, Camera, Cog, DoorOpen, Flame, HardHat, Siren, Truck, Wind } from 'lucide-react';
import { IconNodeBase } from './icon-node-base';
import type {
  CameraNodeData,
  EmergencyResponderNodeData,
  ExitNodeData,
  FireSystemNodeData,
  GasSensorNodeData,
  MachineNodeData,
  RobotNodeData,
  VehicleNodeData,
  WorkerNodeData,
} from '../types';

export function MachineNode({ data, selected }: NodeProps<MachineNodeData>) {
  return (
    <IconNodeBase
      icon={Cog}
      label={data.label}
      severity={data.severity}
      selected={selected}
      pulse={data.statusText === 'fault'}
      withPipelineHandles
    />
  );
}

export function WorkerNode({ data, selected }: NodeProps<WorkerNodeData>) {
  return <IconNodeBase icon={HardHat} label={data.label} severity={data.severity} selected={selected} pulse={data.collapsed} size={36} />;
}

export function VehicleNode({ data, selected }: NodeProps<VehicleNodeData>) {
  return <IconNodeBase icon={Truck} label={data.label} severity={data.severity} selected={selected} size={36} />;
}

export function ExitNode({ data, selected }: NodeProps<ExitNodeData>) {
  return <IconNodeBase icon={DoorOpen} label={data.label} severity={data.severity} selected={selected} pulse={data.statusText === 'blocked'} size={32} />;
}

export function FireSystemNode({ data, selected }: NodeProps<FireSystemNodeData>) {
  return <IconNodeBase icon={Flame} label={data.label} severity={data.severity} selected={selected} pulse={data.statusText === 'discharged'} size={32} />;
}

export function GasSensorNode({ data, selected }: NodeProps<GasSensorNodeData>) {
  return <IconNodeBase icon={Wind} label={`${data.value.toFixed(1)}% LEL`} severity={data.severity} selected={selected} size={32} />;
}

export function CameraNode({ data, selected }: NodeProps<CameraNodeData>) {
  return <IconNodeBase icon={Camera} label={data.eventType === 'normal' ? 'Camera' : data.eventType.replace(/_/g, ' ')} severity={data.severity} selected={selected} pulse={data.eventType !== 'normal'} size={32} />;
}

export function RobotNode({ data, selected }: NodeProps<RobotNodeData>) {
  return <IconNodeBase icon={Bot} label={data.label} severity={data.severity} selected={selected} pulse={data.statusText === 'fault'} size={36} />;
}

export function EmergencyResponderNode({ data, selected }: NodeProps<EmergencyResponderNodeData>) {
  return <IconNodeBase icon={Siren} label={data.label} severity={data.severity} selected={selected} pulse={data.statusText !== 'standby'} size={36} />;
}
