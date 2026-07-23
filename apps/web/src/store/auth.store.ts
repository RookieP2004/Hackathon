import { create } from 'zustand';

/**
 * "Cold state" per ARCHITECTURE.md §7.1 — auth session. Deliberately NOT
 * persisted to localStorage/sessionStorage: the access token lives in memory
 * only, for the lifetime of the tab. Losing it on a hard refresh is
 * acceptable and correct — src/lib/api-client.ts's silent-refresh-on-mount
 * flow re-derives a fresh access token from the httpOnly refresh cookie
 * automatically, so the user never has to re-enter a password just because
 * they reloaded the page.
 */

export interface CurrentUser {
  id: number;
  email: string;
  full_name: string;
  mfa_enabled: boolean;
  status: string;
  default_role: { id: number; name: string; description: string | null };
  scoped_roles: Array<{ role: string; plant_id: number | null; zone_id: number | null }>;
}

interface AuthState {
  accessToken: string | null;
  accessTokenExpiresAt: number | null; // epoch ms
  user: CurrentUser | null;
  status: 'idle' | 'authenticated' | 'unauthenticated';
  setSession: (accessToken: string, expiresInSeconds: number) => void;
  setUser: (user: CurrentUser) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  accessTokenExpiresAt: null,
  user: null,
  status: 'idle',
  setSession: (accessToken, expiresInSeconds) =>
    set({
      accessToken,
      accessTokenExpiresAt: Date.now() + expiresInSeconds * 1000,
      status: 'authenticated',
    }),
  setUser: (user) => set({ user }),
  clear: () => set({ accessToken: null, accessTokenExpiresAt: null, user: null, status: 'unauthenticated' }),
}));
