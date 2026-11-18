import type { NextRequest } from "next/server";

import { proxyGet, proxyMutate } from "@/lib/server/proxy";

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyGet(request, `/api/v1/agents/${id}/versions`, {
    allowedParams: ["limit", "offset"],
  });
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyMutate(request, `/api/v1/agents/${id}/versions`);
}
