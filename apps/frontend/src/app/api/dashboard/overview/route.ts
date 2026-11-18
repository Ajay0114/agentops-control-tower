import type { NextRequest } from "next/server";

import { proxyGet } from "@/lib/server/proxy";

export async function GET(request: NextRequest) {
  return proxyGet(request, "/api/v1/dashboard/overview");
}
