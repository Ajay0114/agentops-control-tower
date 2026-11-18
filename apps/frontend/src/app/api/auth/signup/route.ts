import { NextRequest, NextResponse } from "next/server";

import { authBackendRequest, BackendError } from "@/lib/server/backend";
import { verifyCsrf } from "@/lib/server/csrf";
import { setSessionCookie } from "@/lib/server/session";
import type { CurrentUser } from "@/lib/types";

interface SignupResponseBody {
  session_token: string;
  expires_at: string;
  user: CurrentUser;
}

export async function POST(request: NextRequest) {
  if (!(await verifyCsrf(request))) {
    return NextResponse.json({ detail: "Invalid request" }, { status: 403 });
  }

  let payload: { organization_name?: string; email?: string; password?: string };

  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }

  if (!payload.organization_name || !payload.email || !payload.password) {
    return NextResponse.json(
      { detail: "Organization name, email and password are required" },
      { status: 400 }
    );
  }

  try {
    const { data } = await authBackendRequest<SignupResponseBody>("/api/v1/auth/signup", {
      method: "POST",
      body: {
        organization_name: payload.organization_name,
        email: payload.email,
        password: payload.password,
      },
    });

    await setSessionCookie(data.session_token, data.expires_at);

    return NextResponse.json({ user: data.user }, { status: 201 });
  } catch (error) {
    if (error instanceof BackendError) {
      // Relay the backend's own status (409 duplicate email, 422
      // validation) and its already-generic message.
      return NextResponse.json(error.body ?? { detail: "Signup failed" }, {
        status: error.status,
      });
    }

    console.error("Unexpected error during signup", error);
    return NextResponse.json({ detail: "Unexpected server error" }, { status: 502 });
  }
}
