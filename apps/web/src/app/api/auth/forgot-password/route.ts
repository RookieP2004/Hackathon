import { NextRequest, NextResponse } from 'next/server';
import { IDENTITY_SERVICE_URL } from '@/lib/auth-constants';

/** Thin proxy — no cookie handling needed; see auth_service.request_password_reset's
 * "always returns successfully" anti-enumeration design, mirrored by the UI. */
export async function POST(request: NextRequest) {
  const body = await request.json();
  const backendResponse = await fetch(`${IDENTITY_SERVICE_URL}/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await backendResponse.json();
  return NextResponse.json(data, { status: backendResponse.status });
}
