import type { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const n = request.nextUrl.searchParams.get("n") ?? "20";
  const count = Math.min(Math.max(parseInt(n, 10) || 20, 1), 100);
  return proxyToBackend(`/feed?n=${count}`);
}
