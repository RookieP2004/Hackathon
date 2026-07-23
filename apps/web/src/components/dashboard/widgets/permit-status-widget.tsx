'use client';

import { formatDistanceToNow } from 'date-fns';
import { ClipboardCheck } from 'lucide-react';
import { WidgetCard } from '../widget-card';
import { AllClearState, ErrorState, ListSkeleton } from '../list-states';
import { usePermits } from '@/hooks/use-dashboard-data';
import { cn } from '@/lib/utils';

const STATUS_CLASSES: Record<string, string> = {
  draft: 'text-muted-foreground bg-muted/30 border-border',
  active: 'text-severity-nominal bg-severity-nominal/10 border-severity-nominal/30',
  suspended: 'text-severity-medium bg-severity-medium/10 border-severity-medium/30',
  closed: 'text-muted-foreground bg-muted/30 border-border',
  revoked: 'text-severity-critical bg-severity-critical/10 border-severity-critical/30',
};

export function PermitStatusWidget() {
  const { data, isLoading, isError, error, refetch } = usePermits();
  const permits = data?.items ?? [];
  const activeCount = permits.filter((p) => p.status === 'active').length;

  return (
    <WidgetCard
      title="Permit Status"
      icon={ClipboardCheck}
      accent="indigo"
      headerRight={<span className="text-xs text-muted-foreground">{activeCount} active</span>}
    >
      {isLoading && <ListSkeleton />}
      {isError && <ErrorState message={(error as Error).message} onRetry={() => refetch()} />}
      {!isLoading && !isError && permits.length === 0 && <AllClearState label="No permits on file" />}
      <ul className="space-y-2">
        {permits.map((p) => (
          <li key={p.id} className="flex items-center justify-between rounded-md border border-border/60 px-3 py-2">
            <div>
              <p className="text-sm font-medium text-foreground">{p.permit_number}</p>
              <p className="text-[11px] text-muted-foreground-subtle">
                Expires {formatDistanceToNow(new Date(p.valid_to), { addSuffix: true })}
              </p>
            </div>
            <span className={cn('rounded-full border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide', STATUS_CLASSES[p.status])}>
              {p.status}
            </span>
          </li>
        ))}
      </ul>
    </WidgetCard>
  );
}
