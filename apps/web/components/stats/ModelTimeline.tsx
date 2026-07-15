"use client";

import { useEffect, useRef } from "react";
import type { DailyMetric, ModelInfo } from "@/lib/types";
import { ArrowRightIcon } from "@/components/icons";

interface Segment {
  version: string;
  from: string;
  to: string;
  days: number;
}

/** Collapse the daily series into contiguous model-version date ranges. */
export function deriveSegments(daily: DailyMetric[]): Segment[] {
  const segments: Segment[] = [];
  for (const d of daily) {
    if (!d.model_version) continue;
    const last = segments[segments.length - 1];
    if (last && last.version === d.model_version) {
      last.to = d.day;
      last.days += 1;
    } else {
      segments.push({ version: d.model_version, from: d.day, to: d.day, days: 1 });
    }
  }
  return segments;
}

/** (d) Model version timeline — horizontal badge sequence with date ranges. */
export default function ModelTimeline({
  daily,
  production,
  staging,
}: {
  daily: DailyMetric[];
  production: ModelInfo | null;
  staging: ModelInfo | null;
}) {
  const segments = deriveSegments(daily);
  const railRef = useRef<HTMLDivElement | null>(null);

  // Start the rail scrolled to the newest (current) segment.
  useEffect(() => {
    const el = railRef.current;
    if (el) el.scrollLeft = el.scrollWidth;
  }, []);

  return (
    <div>
      {/* registry status chips */}
      <div className="mb-3 flex flex-wrap gap-2">
        <span className="flex items-center gap-1.5 rounded-sm bg-accent-soft px-2 py-1 font-data text-[11px] text-accent">
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
          production · {production?.version ?? "—"}
        </span>
        <span className="flex items-center gap-1.5 rounded-sm border border-line px-2 py-1 font-data text-[11px] text-ink-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-current opacity-60" />
          staging · {staging?.version ?? "无"}
        </span>
      </div>

      {segments.length === 0 ? (
        <div className="flex h-[96px] items-center justify-center rounded-md border border-dashed border-line-strong">
          <p className="font-data text-[11px] text-ink-faint">
            暂无模型上线记录
          </p>
        </div>
      ) : (
        <div
          ref={railRef}
          className="rail flex items-stretch gap-2 overflow-x-auto pb-1"
        >
          {segments.map((seg, i) => {
            const current = i === segments.length - 1;
            return (
              <div key={`${seg.version}-${seg.from}`} className="flex items-center gap-2">
                <div
                  className={`min-w-[132px] shrink-0 rounded-md border px-3 py-2 ${
                    current
                      ? "border-accent/40 bg-accent-soft"
                      : "border-line bg-raised"
                  }`}
                >
                  <p
                    className={`font-data text-xs font-medium ${
                      current ? "text-accent" : "text-ink"
                    }`}
                  >
                    {seg.version}
                    {current && (
                      <span className="ml-1.5 rounded-sm bg-accent px-1 py-px text-[9px] uppercase tracking-wide text-white">
                        live
                      </span>
                    )}
                  </p>
                  <p className="mt-1 font-data text-[10px] text-ink-faint">
                    {seg.from.slice(5)} → {seg.to.slice(5)}
                  </p>
                  <p className="font-data text-[10px] text-ink-faint">
                    {seg.days} 天在线
                  </p>
                </div>
                {i < segments.length - 1 && (
                  <ArrowRightIcon className="h-3.5 w-3.5 shrink-0 text-ink-faint" />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
