'use client';

import { formatDistanceToNow } from 'date-fns';
import { BellRing } from 'lucide-react';
import { WidgetCard } from '../widget-card';
import { SeverityBadge } from '../severity-badge';
import { AllClearState, ErrorState, ListSkeleton } from '../list-states';
import { fromDomainSeverity } from '../severity';
import { useAlerts } from '@/hooks/use-dashboard-data';

export function LiveAlertsWidget() {
  const { data, isLoading, isError, error } = useAlerts();
  const alerts = data?.items ?? [];
  const openCount = alerts.filter((a) => a.status === 'open').length;
  const worstSeverity = alerts.some((a) => a.status !== 'resolved' && a.severity === 'critical') ? 'critical' : undefined;

  return (
    <WidgetCard
      title="Live Alerts"
      icon={BellRing}
      severity={worstSeverity}
      accent={worstSeverity ? undefined : 'indigo'}
      headerRight={<span className="text-xs text-muted-foreground">{openCount} open</span>}
    >
      {isLoading && <ListSkeleton />}
      {isError && <ErrorState message={(error as Error).message} />}
      {!isLoading && !isError && alerts.length === 0 && <AllClearState label="No alerts raised" />}
      <ul className="space-y-2" aria-live="polite" aria-relevant="additions">
        {alerts.map((a) => (
          <li key={a.id} className="flex flex-col gap-1 rounded-md border border-border/60 px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-foreground">{a.message}</span>
              <SeverityBadge severity={fromDomainSeverity(a.severity)} />
            </div>
            <div className="flex items-center justify-between text-[11px] text-muted-foreground-subtle">
              <span className="uppercase tracking-wide">{a.status}</span>
              <span>{formatDistanceToNow(new Date(a.triggered_at), { addSuffix: true })}</span>
            </div>
          </li>
        ))}
      </ul>
    </WidgetCard>
  );
}
