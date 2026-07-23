import { QueryClient } from '@tanstack/react-query';

/**
 * React Query is the "warm state" cache per ARCHITECTURE.md §7.1 — incidents,
 * playbooks, users — normalized caching with background refetch. It is
 * deliberately NOT used for "hot" live telemetry state, which flows through
 * the Zustand real-time store instead (see src/store) fed directly by the
 * WebSocket client (src/lib/socket.ts), per §7.1's state-management split.
 */
export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  });
}
