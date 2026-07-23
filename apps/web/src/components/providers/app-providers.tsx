'use client';

import { useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { MotionConfig } from 'framer-motion';
import { createQueryClient } from '@/lib/query-client';

/**
 * The single top-level client-side provider tree. Theme provider and auth
 * context are added here as each is implemented (DEVELOPMENT_ROADMAP.md
 * M111-M117) — kept as one composed entry point so `layout.tsx` never needs
 * to know how many providers exist.
 *
 * `MotionConfig reducedMotion="user"` makes every `motion.*` element in the
 * tree honor the OS-level prefers-reduced-motion setting automatically
 * (Framer Motion swaps transform/layout animations for instant changes)
 * without each component needing its own media-query check.
 */
export function AppProviders({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => createQueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
      {process.env.NODE_ENV === 'development' && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
