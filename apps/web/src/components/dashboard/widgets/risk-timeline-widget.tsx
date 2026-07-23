'use client';

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { TrendingUp } from 'lucide-react';
import { WidgetCard } from '../widget-card';
import { computeFactoryHealth } from '@/lib/dashboard-metrics';
import type { TelemetrySnapshot } from '@/lib/services/simulator';

export function RiskTimelineWidget({ history }: { history: TelemetrySnapshot[] }) {
  const data = history.map((snap) => ({
    tick: snap.tick,
    risk: 100 - computeFactoryHealth(snap),
  }));
  const latestRisk = data[data.length - 1]?.risk ?? 0;
  const severity = latestRisk >= 50 ? 'critical' : latestRisk >= 20 ? 'medium' : 'nominal';

  return (
    <WidgetCard title="Risk Timeline" icon={TrendingUp} severity={severity}>
      <ResponsiveContainer width="100%" height={110}>
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
          <XAxis dataKey="tick" hide />
          <YAxis domain={[0, 100]} tick={{ fill: '#9AA4B2', fontSize: 10 }} axisLine={false} tickLine={false} width={28} />
          <Tooltip
            contentStyle={{ background: '#1A1E24', border: '1px solid #252A31', borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: '#F2F4F7' }}
            formatter={(value: number) => [`${value}`, 'Risk']}
            labelFormatter={(tick) => `Tick ${tick}`}
          />
          <Line type="monotone" dataKey="risk" stroke="#4F5FE8" strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-1 text-xs text-muted-foreground">
        Rolling risk index over the last {data.length} ticks (100 − Factory Health)
      </p>
    </WidgetCard>
  );
}
