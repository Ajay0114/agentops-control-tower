import type { NextRequest } from "next/server";

import { proxyGet } from "@/lib/server/proxy";

export async function GET(request: NextRequest) {
  return proxyGet(request, "/api/v1/executions", {
    allowedParams: [
      "session_id",
      "agent_id",
      "environment_id",
      "status",
      "execution_id",
      "started_after",
      "started_before",
      "limit",
      "offset",
    ],
  });
}
