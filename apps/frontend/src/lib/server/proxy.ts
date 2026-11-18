import "server-only";

import { NextRequest, NextResponse } from "next/server";

import { backendRequest, BackendError } from "./backend";
import { verifyCsrf } from "./csrf";
import { getCurrentUser } from "./session";

/**
 * Shared implementation for every GET route handler under app/api/* that
 * forwards to a tenant-scoped backend endpoint. Centralizing this means
 * every resource route applies the exact same rule: validate the dashboard
 * session first (never trust the browser's request on its own), then call
 * the backend with this deployment's own API key - never anything the
 * browser sent - and relay the backend's own response (and, for endpoints
 * like /executions that report one, its X-Total-Count header) back
 * unchanged. See docs/architecture/m7-dashboard-and-auth.md.
 */
export async function proxyGet(
  request: NextRequest,
  backendPath: string,
  options: { allowedParams?: string[] } = {}
): Promise<NextResponse> {
  const user = await getCurrentUser();

  if (!user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const incoming = request.nextUrl.searchParams;
  const forwarded = new URLSearchParams();

  const allowed = options.allowedParams;

  for (const [key, value] of incoming.entries()) {
    if (!allowed || allowed.includes(key)) {
      forwarded.set(key, value);
    }
  }

  try {
    const { data, headers } = await backendRequest<unknown>(backendPath, {
      searchParams: forwarded,
    });

    const response = NextResponse.json(data);
    const totalCount = headers.get("x-total-count");

    if (totalCount !== null) {
      response.headers.set("X-Total-Count", totalCount);
    }

    return response;
  } catch (error) {
    return backendErrorToResponse(error);
  }
}

/**
 * Shared implementation for the API-key-management routes under
 * app/api/settings/api-keys - the one family of requests that must act on
 * behalf of *who is logged in*, not a resource filtered by query params.
 *
 * Gates on the same getCurrentUser() check as proxyGet (401 if neither a
 * real session nor the local-auth bypass applies), then forwards through
 * backendRequest exactly like every other proxied request - the real
 * session token when one exists, or - only when the bypass is active and
 * there genuinely is no session to send - this deployment's own
 * AGENTOPS_API_KEY. The backend's get_auth_context (used by every resource
 * router) and get_key_management_scope (used only by these endpoints)
 * accept the same two credentials for exactly this reason. See
 * docs/architecture/m7-dashboard-and-auth.md section 6.
 */
export async function keyManagementRequest<T>(
  backendPath: string,
  options: { method?: string; body?: unknown; successStatus?: number } = {}
): Promise<NextResponse> {
  const user = await getCurrentUser();

  if (!user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  try {
    const { data } = await backendRequest<T>(backendPath, {
      method: options.method ?? "GET",
      body: options.body,
    });

    return NextResponse.json(data, { status: options.successStatus ?? 200 });
  } catch (error) {
    return backendErrorToResponse(error);
  }
}

/**
 * Shared implementation for the onboarding-wizard mutation routes (create
 * project, create environment) under app/api/* - a logged-in customer
 * creating a resource inside their own organization, as opposed to
 * proxyGet's read-only, filterable resource listing. CSRF-checked like
 * every other state-changing route this app has (login, logout, API-key
 * create/revoke) since it's reachable from a browser form submission.
 */
export async function proxyMutate<T>(
  request: NextRequest,
  backendPath: string,
  options: { successStatus?: number } = {}
): Promise<NextResponse> {
  const user = await getCurrentUser();

  if (!user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  if (!(await verifyCsrf(request))) {
    return NextResponse.json({ detail: "Invalid request" }, { status: 403 });
  }

  let body: unknown;

  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }

  try {
    const { data } = await backendRequest<T>(backendPath, { method: "POST", body });
    return NextResponse.json(data, { status: options.successStatus ?? 201 });
  } catch (error) {
    return backendErrorToResponse(error);
  }
}

export function backendErrorToResponse(error: unknown): NextResponse {
  if (error instanceof BackendError) {
    return NextResponse.json(
      error.body ?? { detail: "Backend request failed" },
      { status: error.status }
    );
  }

  console.error("Unexpected error proxying to backend", error);
  return NextResponse.json({ detail: "Unexpected server error" }, { status: 502 });
}
