import { NextRequest, NextResponse } from "next/server";

import { authBackendRequest, BackendError } from "@/lib/server/backend";
import { verifyCsrf } from "@/lib/server/csrf";
import { setSessionCookie } from "@/lib/server/session";
import type { CurrentUser } from "@/lib/types";

interface LoginResponseBody {
  session_token: string;
  expires_at: string;
  user: CurrentUser;
}

export async function POST(request: NextRequest) {
  if (!(await verifyCsrf(request))) {
    return NextResponse.json({ detail: "Invalid request" }, { status: 403 });
  }

  let payload: { email?: string; password?: string };

  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }

  if (!payload.email || !payload.password) {
    return NextResponse.json({ detail: "Email and password are required" }, { status: 400 });
  }

  try {
    const { data } = await authBackendRequest<LoginResponseBody>("/api/v1/auth/login", {
      method: "POST",
      body: { email: payload.email, password: payload.password },
    });

    await setSessionCookie(data.session_token, data.expires_at);

    return NextResponse.json({ user: data.user });
  } catch (error) {
    if (error instanceof BackendError) {
      // Relay the backend's own status (401 invalid credentials, 429 rate
      // limited) and its already-generic message - never anything more
      // specific that could help an attacker enumerate accounts.
      return NextResponse.json(error.body ?? { detail: "Login failed" }, {
        status: error.status,
      });
    }

    console.error("Unexpected error during login", error);
    return NextResponse.json({ detail: "Unexpected server error" }, { status: 502 });
  }
}
