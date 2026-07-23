import { useAuthStore } from '@/store/auth.store';

/**
 * Client-side auth API surface. Every call here goes through this app's own
 * /api/auth/* Route Handlers (never directly to identity-rbac from the
 * browser) — see those handlers' docstrings for why: the httpOnly refresh
 * cookie must be set/read by the same origin the browser is talking to.
 */

let refreshInFlight: Promise<boolean> | null = null;

/**
 * De-duplicated: if several requests 401 at once (e.g. a batch of parallel
 * dashboard widget fetches), only one refresh call is made and every caller
 * awaits the same in-flight promise, rather than racing multiple rotations
 * against the single-use refresh token (auth_service.py's rotation-on-use
 * would treat the second concurrent refresh as a reuse-of-a-rotated-token
 * theft signal and revoke the whole session — exactly the failure this
 * de-duplication exists to prevent).
 */
async function silentRefresh(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const res = await fetch('/api/auth/refresh', { method: 'POST' });
      if (!res.ok) {
        useAuthStore.getState().clear();
        return false;
      }
      const data = await res.json();
      useAuthStore.getState().setSession(data.access_token, data.expires_in);
      return true;
    } catch {
      useAuthStore.getState().clear();
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

/** Call once on app shell mount to restore a session after a page reload. */
export async function restoreSession(): Promise<void> {
  const ok = await silentRefresh();
  if (!ok) {
    useAuthStore.getState().clear();
    return;
  }
  const me = await fetchWithAuth('/api/auth/me');
  if (me.ok) {
    useAuthStore.getState().setUser(await me.json());
  }
}

/** Fetch wrapper that attaches the bearer token and retries once after a silent refresh on 401. */
export async function fetchWithAuth(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const attempt = async (): Promise<Response> => {
    const token = useAuthStore.getState().accessToken;
    const headers = new Headers(init.headers);
    if (token) headers.set('Authorization', `Bearer ${token}`);
    return fetch(input, { ...init, headers });
  };

  let response = await attempt();

  if (response.status === 401) {
    const refreshed = await silentRefresh();
    if (refreshed) {
      response = await attempt();
    }
  }

  return response;
}

export async function login(email: string, password: string): Promise<{ ok: boolean; error?: string }> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) {
    return { ok: false, error: data.detail ?? 'Login failed' };
  }
  useAuthStore.getState().setSession(data.access_token, data.expires_in);
  const me = await fetchWithAuth('/api/auth/me');
  if (me.ok) {
    useAuthStore.getState().setUser(await me.json());
  }
  return { ok: true };
}

export async function logout(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST' }).catch(() => undefined);
  useAuthStore.getState().clear();
}

export async function forgotPassword(email: string): Promise<{ message: string }> {
  const res = await fetch('/api/auth/forgot-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  return res.json();
}

export async function resetPassword(
  token: string,
  newPassword: string,
): Promise<{ ok: boolean; message: string }> {
  const res = await fetch('/api/auth/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  const data = await res.json();
  return { ok: res.ok, message: data.detail ?? data.message };
}
