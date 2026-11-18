import { NextRequest, NextResponse } from "next/server";

import { verifyCsrf } from "@/lib/server/csrf";
import { keyManagementRequest } from "@/lib/server/proxy";

export async function GET() {
  return keyManagementRequest("/api/v1/auth/api-keys");
}

export async function POST(request: NextRequest) {
  if (!(await verifyCsrf(request))) {
    return NextResponse.json({ detail: "Invalid request" }, { status: 403 });
  }

  const body = await request.json();
  return keyManagementRequest("/api/v1/auth/api-keys", {
    method: "POST",
    body,
    successStatus: 201,
  });
}
