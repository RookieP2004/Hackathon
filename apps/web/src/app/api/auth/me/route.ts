import { NextRequest, NextResponse } from 'next/server';
import { IDENTITY_SERVICE_URL } from '@/lib/auth-constants';

/**
 * Proxies the Authorization header straight through — the access token lives
 * in the client's memory (Zustand store), not a cookie, so it's the caller's
 * job to attach it; this route exists so the browser only ever talks to one
 * origin (this Next.js app), consistent with every other auth route here.
 */
export async function GET(request: NextRequest) {
  const authHeader = request.headers.get('authorization');
  if (!authHeader) {
    return NextResponse.json({ detail: 'Not authenticated' }, { status: 401 });
  }

  const backendResponse = await fetch(`${IDENTITY_SERVICE_URL}/auth/me`, {
    headers: { Authorization: authHeader },
  });
  const data = await backendResponse.json();
  return NextResponse.json(data, { status: backendResponse.status });
}
