import { NextRequest, NextResponse } from "next/server";

import { verifyCsrf } from "@/lib/server/csrf";
import { keyManagementRequest } from "@/lib/server/proxy";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!(await verifyCsrf(request))) {
    return NextResponse.json({ detail: "Invalid request" }, { status: 403 });
  }

  const { id } = await params;
  return keyManagementRequest(`/api/v1/auth/api-keys/${id}/revoke`, { method: "POST" });
}
