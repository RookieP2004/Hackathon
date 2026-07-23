'use client';

import { format } from 'date-fns';
import { Wrench } from 'lucide-react';
import { WidgetCard } from '../widget-card';
import { AllClearState, ErrorState, ListSkeleton } from '../list-states';
import { useMaintenanceRecords } from '@/hooks/use-dashboard-data';
import { cn } from '@/lib/utils';

const STATUS_CLASSES: Record<string, string> = {
  scheduled: 'text-severity-low bg-severity-low/10 border-severity-low/30',
  in_progress: 'text-severity-medium bg-severity-medium/10 border-severity-medium/30',
  completed: 'text-severity-nominal bg-severity-nominal/10 border-severity-nominal/30',
  cancelled: 'text-muted-foreground bg-muted/30 border-border',
};

export function MaintenanceStatusWidget() {
  const { data, isLoading, isError, error } = useMaintenanceRecords();
  const records = data?.items ?? [];
  const pendingCount = records.filter((r) => r.status === 'scheduled' || r.status === 'in_progress').length;

  return (
    <WidgetCard
      title="Maintenance Status"
      icon={Wrench}
      accent="indigo"
      headerRight={<span className="text-xs text-muted-foreground">{pendingCount} pending</span>}
    >
      {isLoading && <ListSkeleton />}
      {isError && <ErrorState message={(error as Error).message} />}
      {!isLoading && !isError && records.length === 0 && <AllClearState label="No work orders on file" />}
      <ul className="space-y-2">
        {records.map((r) => (
          <li key={r.id} className="flex flex-col gap-1 rounded-md border border-border/60 px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-foreground">{r.description}</span>
              <span className={cn('shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide', STATUS_CLASSES[r.status])}>
                {r.status.replace('_', ' ')}
              </span>
            </div>
            {r.scheduled_date && (
              <p className="text-[11px] text-muted-foreground-subtle">
                Scheduled {format(new Date(r.scheduled_date), 'MMM d, yyyy')}
              </p>
            )}
          </li>
        ))}
      </ul>
    </WidgetCard>
  );
}
