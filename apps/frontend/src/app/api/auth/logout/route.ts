import { NextRequest, NextResponse } from "next/server";

import { authBackendRequest } from "@/lib/server/backend";
import { verifyCsrf } from "@/lib/server/csrf";
import { clearSessionCookie, getRawSessionToken } from "@/lib/server/session";

export async function POST(request: NextRequest) {
  if (!(await verifyCsrf(request))) {
    return NextResponse.json({ detail: "Invalid request" }, { status: 403 });
  }

  const token = await getRawSessionToken();

  if (token) {
    try {
      await authBackendRequest("/api/v1/auth/logout", {
        method: "POST",
        body: { session_token: token },
      });
    } catch (error) {
      // Logout must always succeed from the browser's point of view - the
      // cookie is cleared below regardless of whether the backend call
      // itself failed (e.g. the session was already revoked/expired).
      console.error("Backend logout call failed", error);
    }
  }

  await clearSessionCookie();

  return new NextResponse(null, { status: 204 });
}
