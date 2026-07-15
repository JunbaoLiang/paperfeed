import type { EventType, FeedbackEvent } from "@/lib/types";

/**
 * Client-side event tracker (spec §10).
 *
 * - Events buffer in an in-memory queue and flush as a JSON array to
 *   /api/feedback: every 5s if non-empty, on visibilitychange→hidden and
 *   pagehide via navigator.sendBeacon, and immediately for save/dismiss.
 * - Duplicate (impression_id, event_type) pairs are never sent, except
 *   dwell (which is itself fired at most once, with the max measurement).
 * - Dwell measurements are accumulated (max wins) until the next flush;
 *   once a dwell for an impression has been sent, later measurements for
 *   that impression are ignored.
 */

const FLUSH_INTERVAL_MS = 5_000;
const ENDPOINT = "/api/feedback";

type DwellCloser = () => void;

class Tracker {
  private queue: FeedbackEvent[] = [];
  /** `${impression_id}:${event_type}` for every non-dwell event queued or sent. */
  private seen = new Set<string>();
  /** Pending dwell measurements (ms), max per impression, not yet flushed. */
  private pendingDwell = new Map<string, number>();
  /** Impressions whose dwell event has already been flushed. */
  private dwellSent = new Set<string>();
  /** Callbacks that close any in-flight dwell measurement (page hiding). */
  private dwellClosers = new Set<DwellCloser>();
  private intervalId: ReturnType<typeof setInterval> | null = null;
  private started = false;

  /** Idempotent; call once from any client component that tracks events. */
  start(): void {
    if (this.started || typeof window === "undefined") return;
    this.started = true;

    this.intervalId = setInterval(() => this.flush(), FLUSH_INTERVAL_MS);

    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") this.flush(true);
    });
    window.addEventListener("pagehide", () => this.flush(true));
  }

  /** Track a non-dwell event. save/dismiss flush immediately (user intent). */
  track(impressionId: string, eventType: Exclude<EventType, "dwell">): void {
    const key = `${impressionId}:${eventType}`;
    if (this.seen.has(key)) return;
    this.seen.add(key);
    this.queue.push({ impression_id: impressionId, event_type: eventType });

    if (eventType === "save" || eventType === "dismiss") this.flush();
  }

  /**
   * Record a completed dwell measurement (expansion → collapse/off-screen).
   * Multiple measurements for one impression keep the max; the single dwell
   * event is emitted on the next flush.
   */
  recordDwell(impressionId: string, ms: number): void {
    if (ms <= 0 || this.dwellSent.has(impressionId)) return;
    const prev = this.pendingDwell.get(impressionId) ?? 0;
    this.pendingDwell.set(impressionId, Math.max(prev, Math.round(ms)));
  }

  /**
   * Components with an open dwell measurement register a closer so the
   * measurement can be finalized when the page hides mid-read.
   */
  registerDwellCloser(closer: DwellCloser): () => void {
    this.dwellClosers.add(closer);
    return () => this.dwellClosers.delete(closer);
  }

  /** Drain the queue. `useBeacon` for page-hide paths (survives unload). */
  flush(useBeacon = false): void {
    if (useBeacon) {
      // Finalize in-flight dwells before the page goes away.
      for (const close of Array.from(this.dwellClosers)) close();
    }

    // Promote pending dwell measurements to events (fire once per impression).
    for (const [impressionId, ms] of this.pendingDwell) {
      this.queue.push({
        impression_id: impressionId,
        event_type: "dwell",
        value: ms,
      });
      this.dwellSent.add(impressionId);
    }
    this.pendingDwell.clear();

    if (this.queue.length === 0) return;
    const batch = this.queue;
    this.queue = [];
    const payload = JSON.stringify(batch);

    if (useBeacon && typeof navigator.sendBeacon === "function") {
      // text/plain avoids sendBeacon content-type restrictions; the
      // /api/feedback route handler parses the body as JSON regardless.
      const ok = navigator.sendBeacon(
        ENDPOINT,
        new Blob([payload], { type: "text/plain;charset=UTF-8" }),
      );
      if (!ok) this.queue.unshift(...batch);
      return;
    }

    fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
      keepalive: true,
    }).catch(() => {
      // Network hiccup: requeue so the next interval retries.
      this.queue.unshift(...batch);
    });
  }
}

/** Module-level singleton shared by all cards on the page. */
export const tracker = new Tracker();
