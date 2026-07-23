'use client';

import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis } from 'recharts';
import { Wind } from 'lucide-react';
import { WidgetCard } from '../widget-card';
import { worstGasZone } from '@/lib/dashboard-metrics';
import type { TelemetrySnapshot } from '@/lib/services/simulator';

function colorFor(gas: number): string {
  if (gas < 5) return '#2CC295';
  if (gas < 20) return '#E8C547';
  return '#E5484D';
}

export function GasLevelsWidget({ snapshot }: { snapshot: TelemetrySnapshot | null }) {
  const zones = snapshot?.zones ?? [];
  const data = zones.map((z) => ({ name: z.name.split(' ')[0], gas: Math.round(z.ambient.gas_pct_lel * 10) / 10 }));
  const worst = worstGasZone(snapshot);
  const worstSeverity = worst ? worst.ambient.gas_pct_lel >= 20 ? 'critical' : worst.ambient.gas_pct_lel >= 5 ? 'medium' : 'nominal' : 'nominal';

  return (
    <WidgetCard title="Gas Levels" icon={Wind} severity={worstSeverity}>
      <ResponsiveContainer width="100%" height={100}>
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
          <XAxis dataKey="name" tick={{ fill: '#9AA4B2', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip
            cursor={{ fill: 'rgba(255,255,255,0.04)' }}
            contentStyle={{ background: '#1A1E24', border: '1px solid #252A31', borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: '#F2F4F7' }}
            formatter={(value: number) => [`${value}% LEL`, 'Gas']}
          />
          <Bar dataKey="gas" radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.name} fill={colorFor(d.gas)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {worst && (
        <p className="mt-2 text-xs text-muted-foreground">
          Highest: <span className="text-foreground">{worst.name}</span> at{' '}
          <span className="font-mono">{worst.ambient.gas_pct_lel.toFixed(1)}%</span> LEL
        </p>
      )}
    </WidgetCard>
  );
}
