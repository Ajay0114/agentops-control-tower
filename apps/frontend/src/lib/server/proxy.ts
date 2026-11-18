import "server-only";

import { NextRequest, NextResponse } from "next/server";

import { backendRequest, BackendError } from "./backend";
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
