'use client';

import { Area, AreaChart, ResponsiveContainer, YAxis } from 'recharts';

interface SparklinePoint {
  value: number;
}

interface SparklineProps {
  data: SparklinePoint[];
  color: string;
  height?: number;
  domain?: [number, number];
}

/** A minimal trend line with no axes/gridlines/tooltip — dashboard tiles show the shape of a trend, not its exact values (the numeric readout does that). */
export function Sparkline({ data, color, height = 40, domain }: SparklineProps) {
  const gradientId = `spark-${color.replace(/[^a-zA-Z0-9]/g, '')}`;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <YAxis hide domain={domain ?? ['dataMin - 1', 'dataMax + 1']} />
        <Area
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#${gradientId})`}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
