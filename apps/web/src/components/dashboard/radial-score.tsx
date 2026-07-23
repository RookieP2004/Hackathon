'use client';

import { motion } from 'framer-motion';
import type { DashboardSeverity } from './severity';

interface RadialScoreProps {
  score: number; // 0-100
  severity: DashboardSeverity;
  size?: number;
}

const STROKE_COLOR: Record<DashboardSeverity, string> = {
  nominal: '#2CC295',
  low: '#6E8FAE',
  medium: '#E8C547',
  high: '#F5A524',
  critical: '#E5484D',
};

/** A circular progress gauge — the hero visual for Factory Health / Safety Score. */
export function RadialScore({ score, severity, size = 72 }: RadialScoreProps) {
  const stroke = 6;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.max(0, Math.min(100, score)) / 100);

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="currentColor" strokeWidth={stroke} className="text-border" />
      <motion.circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={STROKE_COLOR[severity]}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={circumference}
        initial={{ strokeDashoffset: circumference }}
        animate={{ strokeDashoffset: offset }}
        transition={{ type: 'spring', stiffness: 90, damping: 20 }}
      />
    </svg>
  );
}
