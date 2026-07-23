'use client';

import { useMemo, useRef, useState } from 'react';
import ReactFlow, { Background, BackgroundVariant, Controls, MiniMap, type Edge, type Node } from 'reactflow';
import 'reactflow/dist/style.css';
import { BuildingNode, ZoneNode } from './nodes/region-nodes';
import {
  CameraNode,
  EmergencyResponderNode,
  ExitNode,
  FireSystemNode,
  GasSensorNode,
  MachineNode,
  RobotNode,
  VehicleNode,
  WorkerNode,
} from './nodes/point-nodes';
import { PipelineEdge, type PipelineEdgeData } from './pipeline-edge';
import { ObjectInspector } from './object-inspector';
import { buildMapGraph } from '@/lib/factory-map-builder';
import { resolveInspectorContent } from '@/lib/factory-map-inspector';
import { createAnchorRegistry } from '@/lib/mobile-position';
import type { MapNodeData, MapObjectKind } from './types';
import type { TelemetrySnapshot } from '@/lib/services/simulator';

const NODE_TYPES = {
  building: BuildingNode,
  zone: ZoneNode,
  machine: MachineNode,
  worker: WorkerNode,
  vehicle: VehicleNode,
  exit: ExitNode,
  fireSystem: FireSystemNode,
  gasSensor: GasSensorNode,
  camera: CameraNode,
  robot: RobotNode,
  emergencyResponder: EmergencyResponderNode,
};

const EDGE_TYPES = { pipeline: PipelineEdge };

export function FactoryMapCanvas({ snapshot }: { snapshot: TelemetrySnapshot | null }) {
  const anchorsRef = useRef(createAnchorRegistry());
  const [selected, setSelected] = useState<{ kind: MapObjectKind; id: string } | null>(null);

  const { nodes, edges } = useMemo(() => {
    if (!snapshot) return { nodes: [], edges: [] };
    return buildMapGraph(snapshot, anchorsRef.current);
  }, [snapshot]);

  const inspectorContent = useMemo(() => {
    if (!selected || !snapshot) return null;
    return resolveInspectorContent(selected.kind, selected.id, snapshot);
  }, [selected, snapshot]);

  function handleNodeClick(_event: React.MouseEvent, node: Node) {
    const data = node.data as MapNodeData;
    setSelected({ kind: data.kind, id: data.id });
  }

  function handleEdgeClick(_event: React.MouseEvent, edge: Edge) {
    const data = edge.data as PipelineEdgeData;
    setSelected({ kind: 'pipeline', id: data.pipelineId });
  }

  return (
    <div className="relative h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        edgeTypes={EDGE_TYPES}
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
        onPaneClick={() => setSelected(null)}
        nodesDraggable={false}
        nodesConnectable={false}
        minZoom={0.3}
        maxZoom={2.5}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="#252A31" />
        <Controls showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          nodeColor={(node) => {
            const data = node.data as MapNodeData;
            if (data.severity === 'critical') return '#E5484D';
            if (data.severity === 'high') return '#F5A524';
            if (data.severity === 'medium') return '#E8C547';
            return '#2CC295';
          }}
          maskColor="rgba(10, 12, 15, 0.75)"
          style={{ backgroundColor: '#12151A' }}
        />
      </ReactFlow>
      <ObjectInspector content={inspectorContent} onClose={() => setSelected(null)} />
    </div>
  );
}
