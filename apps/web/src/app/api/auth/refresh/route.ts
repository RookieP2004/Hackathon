import { NextRequest, NextResponse } from 'next/server';
import { IDENTITY_SERVICE_URL, REFRESH_COOKIE } from '@/lib/auth-constants';

/**
 * Reads the httpOnly refresh cookie (never sent by the client explicitly —
 * the browser attaches it automatically), calls identity-rbac's rotation-on-use
 * refresh endpoint, and re-sets the cookie to the newly-issued refresh token.
 * If the presented token was already rotated away (theft-detection chain
 * revocation, app/domain/auth_service.py's _revoke_chain_from), the backend
 * returns 401 and this clears the cookie rather than leaving a dead one behind.
 */
export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;

  if (!refreshToken) {
    return NextResponse.json({ detail: 'No session' }, { status: 401 });
  }

  const backendResponse = await fetch(`${IDENTITY_SERVICE_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  const data = await backendResponse.json();

  if (!backendResponse.ok) {
    const response = NextResponse.json(data, { status: backendResponse.status });
    response.cookies.delete(REFRESH_COOKIE);
    return response;
  }

  const response = NextResponse.json({
    access_token: data.access_token,
    expires_in: data.expires_in,
  });

  response.cookies.set(REFRESH_COOKIE, data.refresh_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: 60 * 60 * 24 * 30,
  });

  return response;
}
