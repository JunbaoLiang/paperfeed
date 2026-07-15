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

  const keywords = (body as { keywords?: unknown })?.keywords;
  if (
    !Array.isArray(keywords) ||
    keywords.length === 0 ||
    !keywords.every((k) => typeof k === "string" && k.trim().length > 0)
  ) {
    return NextResponse.json(
      { error: "keywords must be a non-empty array of strings" },
      { status: 400 },
    );
  }

  return proxyToBackend("/admin/seed-profile", {
    method: "POST",
    body: { keywords: keywords.map((k: string) => k.trim()) },
  });
}
