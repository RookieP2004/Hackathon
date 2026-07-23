'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { restoreSession } from '@/lib/api-client';
import { useAuthStore } from '@/store/auth.store';

/**
 * Belt-and-suspenders alongside middleware.ts: middleware only checks cookie
 * *presence* (fast, edge-runtime, no DB round-trip); this layout actually
 * restores a real access token from the httpOnly refresh cookie on mount via
 * a silent refresh call, and redirects to /login if that fails (e.g. the
 * refresh token was valid-looking to the cookie check but has since expired
 * or been revoked server-side).
 */
export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const status = useAuthStore((s) => s.status);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (status === 'authenticated') {
      setChecked(true);
      return;
    }
    restoreSession().finally(() => setChecked(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (checked && useAuthStore.getState().status !== 'authenticated') {
      router.replace('/login');
    }
  }, [checked, router]);

  if (!checked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted border-t-primary" />
      </div>
    );
  }

  return <>{children}</>;
}
