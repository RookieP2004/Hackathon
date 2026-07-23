'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { HardHat, X } from 'lucide-react';
import { severityStyles } from '@/components/dashboard/severity';
import { RadialScore } from '@/components/dashboard/radial-score';
import type { InspectorContent } from '@/lib/factory-map-inspector';

interface ObjectInspectorProps {
  content: InspectorContent | null;
  onClose: () => void;
}

export function ObjectInspector({ content, onClose }: ObjectInspectorProps) {
  return (
    <AnimatePresence>
      {content && (
        <motion.aside
          initial={{ x: 360, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 360, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 320, damping: 32 }}
          className="absolute right-4 top-4 z-20 flex max-h-[calc(100%-2rem)] w-[340px] flex-col overflow-hidden rounded-lg border border-border bg-card-raised shadow-2xl"
        >
          <header className="flex items-start justify-between gap-2 border-b border-border/60 px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-foreground">{content.title}</h2>
              <p className="text-xs text-muted-foreground-subtle">{content.subtitle}</p>
            </div>
            <button onClick={onClose} aria-label="Close panel" className="rounded p-1 text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </header>

          <div className="flex-1 space-y-4 overflow-y-auto p-4">
            <section className="flex items-center gap-3">
              {content.health !== null ? (
                <RadialScore score={content.health} severity={content.severity} size={56} />
              ) : (
                <div className={`h-14 w-14 rounded-full border-2 ${severityStyles(content.severity).border} flex items-center justify-center`}>
                  <HardHat className={`h-6 w-6 ${severityStyles(content.severity).text}`} />
                </div>
              )}
              <div>
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Current Status</p>
                <p className="text-sm font-medium capitalize text-foreground">{content.status.replace(/_/g, ' ')}</p>
                <span className={`mt-1 inline-block rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase ${severityStyles(content.severity).border} ${severityStyles(content.severity).bg} ${severityStyles(content.severity).text}`}>
                  Risk: {severityStyles(content.severity).label}
                </span>
              </div>
            </section>

            <section>
              <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Alerts</p>
              {content.alerts.length === 0 ? (
                <p className="text-xs text-severity-nominal">No active alerts</p>
              ) : (
                <ul className="space-y-1">
                  {content.alerts.map((alert, i) => (
                    <li key={i} className="rounded-md border border-severity-critical/30 bg-severity-critical/10 px-2 py-1.5 text-xs capitalize text-severity-critical">
                      {alert}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {content.liveData.length > 0 && (
              <section>
                <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Live Sensor Data</p>
                <dl className="grid grid-cols-2 gap-x-2 gap-y-1.5">
                  {content.liveData.map((reading) => (
                    <div key={reading.label} className="rounded-md bg-muted/20 px-2 py-1.5">
                      <dt className="text-[10px] text-muted-foreground-subtle">{reading.label}</dt>
                      <dd className="font-mono text-sm tabular-nums text-foreground">{reading.value}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            )}

            <section>
              <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Worker Presence {content.workersPresent.length > 0 && `(${content.workersPresent.length})`}
              </p>
              {content.workersPresent.length === 0 ? (
                <p className="text-xs text-muted-foreground-subtle">No workers currently present</p>
              ) : (
                <ul className="space-y-1">
                  {content.workersPresent.map((w) => (
                    <li key={w.worker_id} className="flex items-center justify-between rounded-md bg-muted/20 px-2 py-1.5 text-xs">
                      <span className="text-foreground">{w.name}</span>
                      <span className="text-muted-foreground-subtle">{w.status}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
