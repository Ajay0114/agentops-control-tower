import type { NextRequest } from "next/server";

import { proxyMutate } from "@/lib/server/proxy";

export async function POST(request: NextRequest) {
  return proxyMutate(request, "/api/v1/projects");
}
