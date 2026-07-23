/**
 * Shared constants between the Route Handlers (server) and middleware.
 * REFRESH_COOKIE is httpOnly + secure + sameSite=lax — never readable by
 * client-side JS, per ARCHITECTURE.md §20's bearer-token handling and the
 * XSS-mitigation rationale documented in the Route Handlers themselves.
 */
export const REFRESH_COOKIE = "aegis_refresh_token";
// 127.0.0.1, not "localhost": Node's server-side fetch() (used by every Route
// Handler in this directory) can resolve "localhost" to the IPv6 loopback
// (::1) first on some Windows/Node version combinations, which then fails to
// connect when the target service only binds IPv4 -- confirmed by actually
// hitting this exact ECONNREFUSED ::1 failure while testing the login flow
// against a locally-running (non-Docker) identity-rbac instance, the same
// `make web` + bare `uvicorn` local-dev combination this default is for.
export const IDENTITY_SERVICE_URL =
  process.env.IDENTITY_SERVICE_URL ?? "http://127.0.0.1:8012";
