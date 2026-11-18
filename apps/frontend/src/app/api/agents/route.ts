import type { NextRequest } from "next/server";

import { proxyGet } from "@/lib/server/proxy";

export async function GET(request: NextRequest) {
  return proxyGet(request, "/api/v1/agents", {
    allowedParams: ["environment_id", "status", "limit", "offset"],
  });
}
