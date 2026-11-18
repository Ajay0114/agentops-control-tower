import type { NextRequest } from "next/server";

import { proxyGet } from "@/lib/server/proxy";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ traceId: string }> }
) {
  const { traceId } = await params;
  return proxyGet(request, `/api/v1/telemetry/traces/${traceId}/events`, {
    allowedParams: ["page", "page_size"],
  });
}
