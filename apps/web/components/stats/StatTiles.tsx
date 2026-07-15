"use client";

import type { DailyMetric, ModelInfo } from "@/lib/types";

function compact(n: number): string {
  if (n >= 10_000) return `${(n / 1000).toFixed(1)}K`;
  return n.toLocaleString();
}

function Tile({
  label,
  value,
  sub,
  accent = false,
  mono = false,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: boolean;
  mono?: boolean;
}) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4 shadow-card">
      <p className="text-xs text-ink-muted">{label}</p>
      <p
        className={`mt-1.5 font-semibold leading-tight ${
          mono ? "font-data text-base break-all" : "text-2xl leading-none"
        } ${accent ? "text-accent" : ""}`}
      >
        {value}
      </p>
      {sub && (
        <p className="mt-1.5 font-data text-[10px] uppercase tracking-[0.12em] text-ink-faint">
          {sub}
        </p>
      )}
    </div>
  );
}

/** (e) Headline stat tiles for the last-90-day window. */
export default function StatTiles({
  daily,
  production,
  interactionCount,
}: {
  daily: DailyMetric[];
  production: ModelInfo | null;
  interactionCount: number;
}) {
  const impressions = daily.reduce((s, d) => s + d.impressions, 0);
  const clicks = daily.reduce((s, d) => s + d.clicks, 0);
  const saves = daily.reduce((s, d) => s + d.saves, 0);
  const ctr = impressions > 0 ? (clicks / impressions) * 100 : 0;

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Tile
        label="总曝光"
        value={compact(impressions)}
        sub="impressions · 90d"
      />
      <Tile
        label="整体 CTR"
        value={impressions > 0 ? `${ctr.toFixed(1)}%` : "—"}
        sub={`${compact(clicks)} clicks`}
        accent
      />
      <Tile
        label="收藏"
        value={compact(saves)}
        sub={`profile events ${compact(interactionCount)}`}
      />
      <Tile
        label="当前模型"
        value={production?.version ?? "—"}
        mono
        sub={
          production
            ? `${production.model_type} · production`
            : "no production model"
        }
      />
    </div>
  );
}
