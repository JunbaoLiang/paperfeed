"use client";

import type { TooltipPayloadEntry } from "recharts";

/** Card shell shared by every chart on the stats page. */
export function ChartCard({
  title,
  subtitle,
  headline,
  children,
}: {
  title: string;
  subtitle: string;
  headline?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-line bg-surface p-4 shadow-card sm:p-5">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium">{title}</h2>
          <p className="mt-0.5 font-data text-[10px] uppercase tracking-[0.15em] text-ink-faint">
            {subtitle}
          </p>
        </div>
        {headline && (
          <span className="shrink-0 font-data text-lg font-medium">
            {headline}
          </span>
        )}
      </div>
      {children}
    </section>
  );
}

/** Static legend row — series identity never relies on color-matching alone. */
export function LegendRow({
  entries,
}: {
  entries: { label: string; color: string }[];
}) {
  return (
    <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1">
      {entries.map((e) => (
        <span
          key={e.label}
          className="flex items-center gap-1.5 text-xs text-ink-muted"
        >
          <span
            className="h-2.5 w-2.5 rounded-[3px]"
            style={{ backgroundColor: e.color }}
          />
          {e.label}
        </span>
      ))}
    </div>
  );
}

/**
 * Shared tooltip: theme surface, hairline border, mono numbers.
 * Text wears ink tokens; the colored dot beside each row carries identity.
 */
export function ChartTip({
  active,
  payload,
  label,
  format,
}: {
  active?: boolean;
  payload?: ReadonlyArray<TooltipPayloadEntry>;
  label?: string | number;
  format?: (value: number) => string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2 shadow-card">
      <p className="mb-1 font-data text-[11px] text-ink-faint">{String(label)}</p>
      {payload.map((entry) => (
        <p
          key={String(entry.dataKey)}
          className="flex items-center gap-1.5 font-data text-xs text-ink"
        >
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-ink-muted">{entry.name}</span>
          <span className="ml-auto pl-3 font-medium tabular-nums">
            {typeof entry.value === "number"
              ? (format?.(entry.value) ?? entry.value.toLocaleString())
              : String(entry.value)}
          </span>
        </p>
      ))}
    </div>
  );
}

/** Placeholder when a chart has no data yet. */
export function EmptyChart({ hint }: { hint: string }) {
  return (
    <div className="flex h-[220px] flex-col items-center justify-center rounded-md border border-dashed border-line-strong">
      <p className="text-sm text-ink-muted">暂无数据</p>
      <p className="mt-1 px-6 text-center font-data text-[11px] text-ink-faint">
        {hint}
      </p>
    </div>
  );
}
