import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { authBackendRequest, BackendError } from "./backend";
import { SESSION_COOKIE_NAME, isProduction } from "./env";
import type { CurrentUser } from "@/lib/types";

/**
 * The trust boundary (see docs/architecture/m7-dashboard-and-auth.md):
 * the browser only ever holds an HTTP-only, opaque session cookie. Every
 * server-rendered page and every /api/* route handler that needs to know
 * "who is this" re-validates that cookie's token against the backend's
 * /api/v1/auth/me on every request - nothing about the user's identity or
 * tenant scope is ever read from anything the browser supplies directly
 * (a query param, a client-side header, etc). This user's own
 * organization_id/project_id is informational only: the ACTUAL
 * authorization for every data request still flows through the separate,
 * unmodified AuthContext/API-key mechanism (see backendRequest).
 */

export async function getRawSessionToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(SESSION_COOKIE_NAME)?.value ?? null;
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const token = await getRawSessionToken();

  if (!token) {
    return null;
  }

  try {
    const { data } = await authBackendRequest<CurrentUser>("/api/v1/auth/me", {
      headers: { "X-Session-Token": token },
    });
    return data;
  } catch (error) {
    if (error instanceof BackendError && error.status === 401) {
      return null;
    }
    throw error;
  }
}

/** For Server Components/layouts: redirects to /login if there is no valid session. */
export async function requireUserOrRedirect(): Promise<CurrentUser> {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  return user;
}

export async function setSessionCookie(token: string, expiresAt: string): Promise<void> {
  const store = await cookies();

  store.set(SESSION_COOKIE_NAME, token, {
    httpOnly: true,
    secure: isProduction,
    sameSite: "lax",
    path: "/",
    expires: new Date(expiresAt),
  });
}

export async function clearSessionCookie(): Promise<void> {
  const store = await cookies();
  store.delete(SESSION_COOKIE_NAME);
}
