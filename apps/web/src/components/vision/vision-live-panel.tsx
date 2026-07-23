'use client';

import { Eye } from 'lucide-react';
import { WidgetCard } from '../dashboard/widget-card';
import { SeverityBadge } from '../dashboard/severity-badge';
import { AllClearState, ListSkeleton } from '../dashboard/list-states';
import type { VisionEvent } from '@/lib/services/vision';
import { detectionClassLabel, severityForDetectionClass } from './detection-severity';

export function VisionLivePanel({ detections, loading }: { detections: VisionEvent[]; loading: boolean }) {
  const worst = detections.some((d) => severityForDetectionClass(d.detection_class) === 'critical')
    ? 'critical'
    : detections.some((d) => severityForDetectionClass(d.detection_class) === 'high')
      ? 'high'
      : undefined;

  return (
    <WidgetCard
      title="Live Detections"
      icon={Eye}
      severity={worst}
      accent={worst ? undefined : 'cyan'}
      headerRight={<span className="text-xs text-muted-foreground">{detections.length} confirmed</span>}
    >
      {loading && <ListSkeleton />}
      {!loading && detections.length === 0 && <AllClearState label="No confirmed detections" />}
      {!loading && detections.length > 0 && (
        <ul className="space-y-2">
          {detections.map((d, i) => (
            <li
              key={`${d.camera_id}-${d.detection_class}-${d.object_id ?? i}`}
              className="flex items-center justify-between gap-3 rounded-md border border-border/60 px-3 py-2"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-foreground">{detectionClassLabel(d.detection_class)}</span>
                  <span className="rounded bg-muted/40 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground-subtle">
                    {d.source === 'yolo_inference' ? 'YOLO' : 'Sim'}
                  </span>
                </div>
                <p className="truncate text-[11px] text-muted-foreground-subtle">
                  {d.camera_id} · {d.zone_id ?? 'unknown zone'}
                  {d.object_id ? ` · ${d.object_id}` : ''}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="font-mono text-xs tabular-nums text-muted-foreground">
                  {Math.round(d.confidence * d.persistence_factor * 100)}%
                </span>
                <SeverityBadge severity={severityForDetectionClass(d.detection_class)} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </WidgetCard>
  );
}
