import { NextResponse, type NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

const EVENT_TYPES = new Set([
  "visible",
  "click_abstract",
  "click_pdf",
  "save",
  "dismiss",
  "dwell",
]);

interface RawEvent {
  impression_id?: unknown;
  event_type?: unknown;
  value?: unknown;
}

function isValidEvent(e: RawEvent): boolean {
  return (
    typeof e === "object" &&
    e !== null &&
    typeof e.impression_id === "string" &&
    typeof e.event_type === "string" &&
    EVENT_TYPES.has(e.event_type) &&
    (e.value === undefined || e.value === null || typeof e.value === "number")
  );
}

/**
 * Accepts a single feedback event object OR an array of events.
 * navigator.sendBeacon may deliver the body as text/plain — the body is
 * therefore always read as text and parsed as JSON regardless of the
 * Content-Type header.
 */
export async function POST(request: NextRequest) {
  let parsed: unknown;
  try {
    parsed = JSON.parse(await request.text());
  } catch {
    return NextResponse.json(
      { error: "Body must be valid JSON" },
      { status: 400 },
    );
  }

  const events = Array.isArray(parsed) ? parsed : [parsed];
  if (events.length === 0) {
    return NextResponse.json({ ok: true, count: 0 });
  }
  if (!events.every((e) => isValidEvent(e as RawEvent))) {
    return NextResponse.json(
      {
        error:
          "Each event needs impression_id (string) and a valid event_type",
      },
      { status: 400 },
    );
  }

  return proxyToBackend("/feedback", { method: "POST", body: parsed });
}
