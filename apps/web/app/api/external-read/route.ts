import { NextResponse, type NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Body must be valid JSON" },
      { status: 400 },
    );
  }

  const ref = (body as { ref?: unknown })?.ref;
  if (typeof ref !== "string" || ref.trim().length < 4) {
    return NextResponse.json(
      { error: "ref must be an arXiv id or URL" },
      { status: 400 },
    );
  }

  return proxyToBackend("/external-read", {
    method: "POST",
    body: { ref: ref.trim() },
  });
}
