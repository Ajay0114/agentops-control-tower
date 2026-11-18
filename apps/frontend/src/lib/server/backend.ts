import "server-only";

import { cookies } from "next/headers";

import { BACKEND_API_URL, getBackendApiKey, SESSION_COOKIE_NAME } from "./env";

// Duplicated from lib/server/session.ts's getRawSessionToken (same 2-line
// cookie read) rather than imported: session.ts imports authBackendRequest
// from this file, so importing session.ts back here would be circular.
// This is the same small-duplication tradeoff proxy.ts already makes for
// its own copy of the local-auth-bypass check - see its module comment.
async function getSessionTokenForBackendRequest(): Promise<string | null> {
  const store = await cookies();
  return store.get(SESSION_COOKIE_NAME)?.value ?? null;
}

export class BackendError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown) {
    super(`Backend request failed with status ${status}`);
    this.status = status;
    this.body = body;
  }
}

interface RawRequestOptions {
  method?: string;
  searchParams?: URLSearchParams;
  body?: unknown;
  headers?: Record<string, string>;
}

async function rawRequest<T>(
  path: string,
  { method = "GET", searchParams, body, headers = {} }: RawRequestOptions = {}
): Promise<{ data: T; headers: Headers }> {
  const url = new URL(`${BACKEND_API_URL}${path}`);

  if (searchParams) {
    for (const [key, value] of searchParams.entries()) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    }
  }

  const response = await fetch(url.toString(), {
    method,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    throw new BackendError(response.status, data);
  }

  return { data: data as T, headers: response.headers };
}

interface BackendRequestOptions {
  method?: string;
  searchParams?: URLSearchParams;
  body?: unknown;
}

/**
 * Tenant-scoped call to the FastAPI backend - never a tenant identifier the
 * browser supplied. Every route handler that proxies a resource endpoint
 * (agents, executions, sessions, environments, projects, telemetry,
 * dashboard, API-key management) goes through this one function, so the
 * credential and base URL are defined in exactly one place.
 *
 * Sends the caller's own dashboard session token when one exists - the
 * backend's get_auth_context (see agentops_api/auth.py) resolves that to
 * the signed-up customer's *own* organization/project, which is what makes
 * two separately signed-up customers' dashboards see only their own data.
 * Falls back to this deployment's own internal API key only when there is
 * no session to send - the local-auth-bypass case (see
 * docs/architecture/m7-dashboard-and-auth.md), never anything the browser
 * supplied directly.
 */
export async function backendRequest<T>(
  path: string,
  options: BackendRequestOptions = {}
): Promise<{ data: T; headers: Headers }> {
  const sessionToken = await getSessionTokenForBackendRequest();
  const headers: Record<string, string> = sessionToken
    ? { "X-Session-Token": sessionToken }
    : { Authorization: `Bearer ${getBackendApiKey()}` };

  return rawRequest<T>(path, { ...options, headers });
}

/**
 * Call to the backend's local-auth endpoints (/api/v1/auth/*), which are a
 * deliberately separate concern from the tenant-scoped API-key mechanism
 * above - see auth_service.py's module docstring. Never sends the tenant
 * API key; the caller supplies whatever these endpoints actually need
 * (nothing for login/logout, X-Session-Token for /me).
 */
export async function authBackendRequest<T>(
  path: string,
  options: RawRequestOptions = {}
): Promise<{ data: T; headers: Headers }> {
  return rawRequest<T>(path, options);
}

/** Builds a URLSearchParams from a plain object, skipping undefined/null/empty values. */
export function toSearchParams(
  params: Record<string, string | number | undefined | null>
): URLSearchParams {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, String(value));
    }
  }

  return searchParams;
}
