'use client';

import { formatDistanceToNow } from 'date-fns';
import { FileWarning } from 'lucide-react';
import { WidgetCard } from '../widget-card';
import { SeverityBadge } from '../severity-badge';
import { AllClearState, ErrorState, ListSkeleton } from '../list-states';
import { fromDomainSeverity } from '../severity';
import { useIncidents } from '@/hooks/use-dashboard-data';

export function IncidentFeedWidget() {
  const { data, isLoading, isError, error, refetch } = useIncidents();
  const incidents = data?.items ?? [];
  const openCount = incidents.filter((i) => i.status !== 'closed').length;

  return (
    <WidgetCard
      title="Incident Feed"
      icon={FileWarning}
      accent="indigo"
      headerRight={<span className="text-xs text-muted-foreground">{openCount} open</span>}
    >
      {isLoading && <ListSkeleton />}
      {isError && <ErrorState message={(error as Error).message} onRetry={() => refetch()} />}
      {!isLoading && !isError && incidents.length === 0 && <AllClearState label="No incidents recorded" />}
      <ul className="space-y-2" aria-live="polite" aria-relevant="additions">
        {incidents.map((inc) => (
          <li key={inc.id} className="flex flex-col gap-1 rounded-md border border-border/60 px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">{inc.incident_number}</span>
              <SeverityBadge severity={fromDomainSeverity(inc.severity)} />
            </div>
            {inc.ai_generated_summary && (
              <p className="text-xs text-aegis-cyan">{inc.ai_generated_summary}</p>
            )}
            <div className="flex items-center justify-between text-[11px] text-muted-foreground-subtle">
              <span className="uppercase tracking-wide">{inc.status}</span>
              <span>{formatDistanceToNow(new Date(inc.opened_at), { addSuffix: true })}</span>
            </div>
          </li>
        ))}
      </ul>
    </WidgetCard>
  );
}
