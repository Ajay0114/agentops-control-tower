import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Duplicated from lib/server/env.ts rather than imported: that module is
// guarded with the `server-only` package, which throws when evaluated
// outside a real server/edge runtime (including under Vitest's jsdom test
// environment) - proxy.ts runs in the Edge runtime in production, which is
// a legitimate server context, but test tooling can't tell the difference.
const SESSION_COOKIE_NAME = "agentops_session";
const CSRF_COOKIE_NAME = "agentops_csrf";

/**
 * Fast, optimistic gate: redirects to /login when the session cookie is
 * simply absent, without a network round trip. This is a UX optimization
 * only, not the authoritative check - every protected page's own layout
 * (and every /api/* route handler) independently re-validates the session
 * against the backend on each request (see lib/server/session.ts), since a
 * cookie that merely exists could still be expired or revoked.
 *
 * Named `proxy` (not `middleware`) per Next.js 16's renamed convention -
 * see node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md.
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isPublicPath =
    pathname === "/login" ||
    // Every other /api/* route handler already does its own session check
    // and returns a clean JSON 401 (see lib/server/proxy.ts's proxyGet) -
    // redirecting an unauthenticated API call to /login instead would hand
    // the caller a login-page HTML document where it expected JSON.
    pathname.startsWith("/api/") ||
    pathname.startsWith("/_next") ||
    pathname === "/favicon.ico";

  const hasSession = request.cookies.has(SESSION_COOKIE_NAME);

  let response: NextResponse;

  if (!isPublicPath && !hasSession) {
    const loginUrl = new URL("/login", request.url);
    response = NextResponse.redirect(loginUrl);
  } else {
    response = NextResponse.next();
  }

  // Ensures the CSRF cookie exists before the login page's first render, so
  // the login form can always echo it back as a header.
  if (!request.cookies.has(CSRF_COOKIE_NAME)) {
    response.cookies.set(CSRF_COOKIE_NAME, crypto.randomUUID(), {
      httpOnly: false,
      sameSite: "lax",
      path: "/",
    });
  }

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
