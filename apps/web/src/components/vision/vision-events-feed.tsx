'use client';

import { formatDistanceToNow } from 'date-fns';
import { History } from 'lucide-react';
import { WidgetCard } from '../dashboard/widget-card';
import { SeverityBadge } from '../dashboard/severity-badge';
import { AllClearState, ListSkeleton } from '../dashboard/list-states';
import type { VisionEvent } from '@/lib/services/vision';
import { detectionClassLabel, severityForDetectionClass } from './detection-severity';

export function VisionEventsFeed({ events, loading }: { events: VisionEvent[]; loading: boolean }) {
  return (
    <WidgetCard title="Vision Events" icon={History} accent="indigo" headerRight={<span className="text-xs text-muted-foreground">last {events.length}</span>}>
      {loading && <ListSkeleton />}
      {!loading && events.length === 0 && <AllClearState label="No events yet this session" />}
      {!loading && events.length > 0 && (
        <ul className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
          {events.map((e, i) => (
            <li key={`${e.observed_at}-${e.camera_id}-${e.detection_class}-${i}`} className="flex items-center justify-between gap-3 rounded-md border border-border/60 px-3 py-2">
              <div className="min-w-0">
                <span className="text-sm text-foreground">
                  {detectionClassLabel(e.detection_class)} at {e.camera_id}
                </span>
                <p className="truncate text-[11px] text-muted-foreground-subtle">
                  {e.zone_id ?? 'unknown zone'} · confidence {Math.round(e.confidence * e.persistence_factor * 100)}%
                </p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                <SeverityBadge severity={severityForDetectionClass(e.detection_class)} />
                <span className="text-[10px] text-muted-foreground-subtle">
                  {formatDistanceToNow(new Date(e.observed_at), { addSuffix: true })}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </WidgetCard>
  );
}
