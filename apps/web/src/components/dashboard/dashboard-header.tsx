'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Box, Eye, LayoutDashboard, Map as MapIcon, ShieldAlert } from 'lucide-react';
import { logout } from '@/lib/api-client';
import { useAuthStore } from '@/store/auth.store';
import { LiveIndicator } from './live-indicator';
import type { FeedStatus } from '@/hooks/use-simulator-feed';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Command Center', icon: LayoutDashboard },
  { href: '/map', label: 'Factory Map', icon: MapIcon },
  { href: '/twin', label: '3D Digital Twin', icon: Box },
  { href: '/vision', label: 'Vision AI', icon: Eye },
];

export function DashboardHeader({ feedStatus }: { feedStatus: FeedStatus }) {
  const router = useRouter();
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  async function handleLogout() {
    await logout();
    router.push('/login');
  }

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-background/80 px-4 py-3 backdrop-blur sm:px-6 sm:py-4">
      <div className="flex items-center gap-3">
        <ShieldAlert className="h-6 w-6 shrink-0 text-aegis-indigo" aria-hidden="true" />
        <div>
          <h1 className="text-sm font-semibold tracking-wide text-foreground">AEGIS AI</h1>
          <p className="hidden text-[11px] text-muted-foreground-subtle sm:block">Aegis Demo Refinery</p>
        </div>
      </div>

      <nav aria-label="Primary" className="order-last flex w-full items-center gap-1 overflow-x-auto rounded-md border border-border bg-muted/10 p-1 sm:order-none sm:w-auto">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-label={item.label}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'flex shrink-0 items-center gap-1.5 rounded px-2.5 py-1.5 text-xs font-medium transition-colors sm:px-3',
                active ? 'bg-aegis-indigo text-white' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <item.icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span className="hidden lg:inline">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="flex items-center gap-3 sm:gap-5">
        <LiveIndicator status={feedStatus} />
        {now && (
          <span className="hidden font-mono text-xs tabular-nums text-muted-foreground md:inline">
            {now.toLocaleTimeString('en-GB')}
          </span>
        )}
        {user && (
          <div className="hidden text-right text-xs xl:block">
            <p className="text-foreground">{user.full_name}</p>
            <p className="text-muted-foreground-subtle">{user.default_role.name.replace(/_/g, ' ')}</p>
          </div>
        )}
        <button
          onClick={handleLogout}
          aria-label="Log out"
          className="rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          Log out
        </button>
      </div>
    </header>
  );
}
