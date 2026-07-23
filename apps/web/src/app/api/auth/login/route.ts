import { NextRequest, NextResponse } from 'next/server';
import { IDENTITY_SERVICE_URL, REFRESH_COOKIE } from '@/lib/auth-constants';

/**
 * Server-side proxy to identity-rbac's POST /auth/login. The refresh token
 * never reaches client-side JavaScript — it's set here as an httpOnly cookie,
 * directly mitigating token theft via XSS (ARCHITECTURE.md §20's bearer-token
 * handling). Only the short-lived access token is returned in the JSON body,
 * for the client to hold in memory (see src/store/auth.store.ts).
 */
export async function POST(request: NextRequest) {
  const body = await request.json();

  const backendResponse = await fetch(`${IDENTITY_SERVICE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const data = await backendResponse.json();

  if (!backendResponse.ok) {
    return NextResponse.json(data, { status: backendResponse.status });
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
    maxAge: 60 * 60 * 24 * 30, // 30 days — matches REFRESH_TOKEN_EXPIRE_DAYS
  });

  return response;
}
