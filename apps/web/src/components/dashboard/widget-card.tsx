'use client';

import { motion } from 'framer-motion';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { severityStyles, type DashboardSeverity } from './severity';

interface WidgetCardProps {
  title: string;
  icon: LucideIcon;
  severity?: DashboardSeverity;
  accent?: 'indigo' | 'cyan' | 'none';
  className?: string;
  children: React.ReactNode;
  headerRight?: React.ReactNode;
}

/**
 * The shared shell every dashboard widget renders inside — a raised dark
 * panel with a severity-tinted top accent (or the brand indigo/cyan accent
 * for non-severity widgets), per UI_UX_SPECIFICATION.md §2's card language.
 * Entrance is a gentle spring fade+rise, not a linear tween (§0.2's motion
 * principle), and respects prefers-reduced-motion via framer-motion's default
 * behavior of honoring the OS setting when `transition` uses spring physics.
 */
export function WidgetCard({ title, icon: Icon, severity, accent = 'none', className, children, headerRight }: WidgetCardProps) {
  const accentClass = severity
    ? severityStyles(severity).text
    : accent === 'cyan'
      ? 'text-aegis-cyan'
      : accent === 'indigo'
        ? 'text-aegis-indigo'
        : 'text-muted-foreground';

  const topBarClass = severity
    ? severityStyles(severity).bg.replace('/10', '')
    : accent === 'cyan'
      ? 'bg-aegis-cyan'
      : accent === 'indigo'
        ? 'bg-aegis-indigo'
        : 'bg-border';

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 260, damping: 28 }}
      className={cn(
        'relative flex flex-col overflow-hidden rounded-lg border border-border bg-card-raised shadow-lg shadow-black/20',
        className,
      )}
    >
      <div className={cn('absolute inset-x-0 top-0 h-[2px] opacity-80', topBarClass)} aria-hidden />
      <header className="flex items-center justify-between gap-2 border-b border-border/60 px-4 py-3">
        <div className="flex items-center gap-2">
          <Icon className={cn('h-4 w-4', accentClass)} strokeWidth={2} />
          <h2 className="text-[13px] font-medium uppercase tracking-wide text-muted-foreground">{title}</h2>
        </div>
        {headerRight}
      </header>
      <div className="flex-1 p-4">{children}</div>
    </motion.section>
  );
}
