import type { NextRequest } from "next/server";

import { proxyGet } from "@/lib/server/proxy";

export async function GET(request: NextRequest) {
  return proxyGet(request, "/api/v1/sessions", {
    allowedParams: ["project_id", "environment_id", "status", "limit", "offset"],
  });
}
