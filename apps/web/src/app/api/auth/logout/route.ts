import { NextRequest, NextResponse } from 'next/server';
import { IDENTITY_SERVICE_URL, REFRESH_COOKIE } from '@/lib/auth-constants';

export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;

  if (refreshToken) {
    // Best-effort: revoke server-side, but always clear the cookie regardless
    // of whether the backend call succeeds — a user clicking "log out" must
    // never be left in a logged-in-looking state due to a transient network error.
    await fetch(`${IDENTITY_SERVICE_URL}/auth/logout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).catch(() => undefined);
  }

  const response = NextResponse.json({ message: 'Logged out' });
  response.cookies.delete(REFRESH_COOKIE);
  return response;
}
