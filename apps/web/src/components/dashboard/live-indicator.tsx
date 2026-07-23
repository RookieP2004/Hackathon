'use client';

import { cn } from '@/lib/utils';
import type { FeedStatus } from '@/hooks/use-simulator-feed';

const STATUS_COPY: Record<FeedStatus, string> = {
  connecting: 'Connecting…',
  live: 'Live',
  stale: 'Feed stale',
  reconnecting: 'Reconnecting…',
};

export function LiveIndicator({ status }: { status: FeedStatus }) {
  const dotClass =
    status === 'live'
      ? 'bg-severity-nominal'
      : status === 'stale'
        ? 'bg-severity-medium'
        : 'bg-muted-foreground-subtle';

  return (
    <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
      <span className="relative flex h-2 w-2">
        {status === 'live' && (
          <span className={cn('absolute inline-flex h-full w-full animate-ping rounded-full opacity-60', dotClass)} />
        )}
        <span className={cn('relative inline-flex h-2 w-2 rounded-full', dotClass)} />
      </span>
      {STATUS_COPY[status]}
    </div>
  );
}
