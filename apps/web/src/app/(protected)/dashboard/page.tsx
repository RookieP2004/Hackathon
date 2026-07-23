'use client';

import { motion } from 'framer-motion';
import { DashboardHeader } from '@/components/dashboard/dashboard-header';
import { ScenarioControlPanel } from '@/components/dashboard/scenario-control-panel';
import { FactoryHealthWidget } from '@/components/dashboard/widgets/factory-health-widget';
import { SafetyScoreWidget } from '@/components/dashboard/widgets/safety-score-widget';
import { WorkersOnlineWidget } from '@/components/dashboard/widgets/workers-online-widget';
import { MachineHealthWidget } from '@/components/dashboard/widgets/machine-health-widget';
import { GasLevelsWidget } from '@/components/dashboard/widgets/gas-levels-widget';
import { EmergencyStatusWidget } from '@/components/dashboard/widgets/emergency-status-widget';
import { RiskTimelineWidget } from '@/components/dashboard/widgets/risk-timeline-widget';
import { IncidentFeedWidget } from '@/components/dashboard/widgets/incident-feed-widget';
import { WeatherWidget } from '@/components/dashboard/widgets/weather-widget';
import { ProductionStatusWidget } from '@/components/dashboard/widgets/production-status-widget';
import { PermitStatusWidget } from '@/components/dashboard/widgets/permit-status-widget';
import { MaintenanceStatusWidget } from '@/components/dashboard/widgets/maintenance-status-widget';
import { LiveAlertsWidget } from '@/components/dashboard/widgets/live-alerts-widget';
import { useSimulatorFeed } from '@/hooks/use-simulator-feed';
import { useWorldTopology } from '@/hooks/use-dashboard-data';

/**
 * The real Dashboard (Command Center) — UI_UX_SPECIFICATION.md §2 / M120-M122,
 * replacing the auth-loop placeholder. Two data sources feed it, deliberately
 * kept separate per ARCHITECTURE.md §7.1's hot/warm state split:
 *   - "hot" state: the iot-simulator's WebSocket telemetry feed (sub-second,
 *     drives Factory Health / Safety Score / Workers Online / Machine Health /
 *     Gas Levels / Emergency Status / Risk Timeline / Production Status)
 *   - "warm" state: real REST reads against incident-service, ingestion-gateway,
 *     and predictive-risk-engine via React Query (15s poll, drives Incident
 *     Feed / Permit Status / Maintenance Status / Weather / Live Alerts)
 */
export default function DashboardPage() {
  const { status, snapshot, history } = useSimulatorFeed();
  const { data: world } = useWorldTopology();
  const isStale = status === 'stale' || status === 'reconnecting';

  return (
    <div className="min-h-screen bg-background">
      <DashboardHeader feedStatus={status} />

      <main className="mx-auto max-w-[1800px] space-y-4 p-6">
        <ScenarioControlPanel world={world} snapshot={snapshot} />

        <div className="relative grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-12">
          {isStale && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="pointer-events-none absolute inset-0 z-10 rounded-lg"
              style={{
                backgroundImage:
                  'repeating-linear-gradient(45deg, rgba(245,165,36,0.06) 0 10px, transparent 10px 20px)',
              }}
              aria-hidden
            />
          )}

          <div className="lg:col-span-3"><FactoryHealthWidget snapshot={snapshot} /></div>
          <div className="lg:col-span-3"><SafetyScoreWidget snapshot={snapshot} /></div>
          <div className="lg:col-span-3"><WorkersOnlineWidget snapshot={snapshot} /></div>
          <div className="lg:col-span-3"><EmergencyStatusWidget snapshot={snapshot} /></div>

          <div className="lg:col-span-4"><MachineHealthWidget snapshot={snapshot} /></div>
          <div className="lg:col-span-4"><GasLevelsWidget snapshot={snapshot} /></div>
          <div className="lg:col-span-4"><RiskTimelineWidget history={history} /></div>

          <div className="lg:col-span-6"><ProductionStatusWidget snapshot={snapshot} /></div>
          <div className="lg:col-span-6"><WeatherWidget /></div>

          <div className="lg:col-span-3"><IncidentFeedWidget /></div>
          <div className="lg:col-span-3"><LiveAlertsWidget /></div>
          <div className="lg:col-span-3"><PermitStatusWidget /></div>
          <div className="lg:col-span-3"><MaintenanceStatusWidget /></div>
        </div>
      </main>
    </div>
  );
}
