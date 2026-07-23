import { NextRequest, NextResponse } from 'next/server';
import { REFRESH_COOKIE } from '@/lib/auth-constants';

/**
 * Route-level gating based on the httpOnly refresh cookie's presence only —
 * NOT full JWT signature verification (that happens per-request against the
 * access token at the API layer, matching ARCHITECTURE.md §21.3's "enforced
 * at the API/data layer, UI is a convenience" principle; a user with no
 * cookie is redirected to /login here as a UX nicety, but a forged/expired
 * access token is still rejected by identity-rbac's get_current_user
 * dependency regardless of what this middleware decided).
 */

const PROTECTED_PREFIXES = ['/dashboard', '/map', '/twin', '/vision'];
const AUTH_PAGES = ['/login', '/forgot-password', '/reset-password'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has(REFRESH_COOKIE);

  const isProtected = PROTECTED_PREFIXES.some((p) => pathname.startsWith(p));
  const isAuthPage = AUTH_PAGES.some((p) => pathname.startsWith(p));

  if (isProtected && !hasSession) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('next', pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (isAuthPage && hasSession && pathname !== '/reset-password') {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*', '/map/:path*', '/twin/:path*', '/vision/:path*', '/login', '/forgot-password', '/reset-password'],
};
