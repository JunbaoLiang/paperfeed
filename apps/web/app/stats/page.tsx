"use client";

import { useCallback, useEffect, useState } from "react";
import type { StatsResponse } from "@/lib/types";
import StatTiles from "@/components/stats/StatTiles";
import ModelTimeline from "@/components/stats/ModelTimeline";
import {
  CtrChart,
  DriftChart,
  EngagementChart,
} from "@/components/stats/charts";
import { ChartCard, EmptyChart } from "@/components/stats/ChartBits";

function StatsSkeleton() {
  return (
    <div aria-busy="true">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <div
            key={i}
            className="rounded-lg border border-line bg-surface p-4 shadow-card"
          >
            <div className="skeleton h-3 w-16" />
            <div className="skeleton mt-2 h-7 w-20" />
            <div className="skeleton mt-2 h-2.5 w-24" />
          </div>
        ))}
      </div>
      {[0, 1].map((i) => (
        <div
          key={i}
          className="mt-4 rounded-lg border border-line bg-surface p-5 shadow-card"
        >
          <div className="skeleton mb-4 h-4 w-40" />
          <div className="skeleton h-[210px] w-full" />
        </div>
      ))}
    </div>
  );
}

export default function StatsPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // setState only inside promise callbacks — keeps the effect body clean.
  const doLoad = useCallback(() => {
    fetch("/api/stats")
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.error ?? `请求失败(HTTP ${res.status})`);
        }
        return res.json() as Promise<StatsResponse>;
      })
      .then(setStats)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "加载失败,请稍后重试"),
      );
  }, []);

  const retry = useCallback(() => {
    setError(null);
    setStats(null);
    doLoad();
  }, [doLoad]);

  useEffect(() => {
    doLoad();
  }, [doLoad]);

  // Ensure ascending day order regardless of what the backend returns.
  const daily = stats
    ? [...stats.daily].sort((a, b) => a.day.localeCompare(b.day))
    : [];
  const hasData = daily.length > 0;

  return (
    <div className="mx-auto max-w-5xl px-4 pt-6 pb-10">
      <div className="mb-5 flex items-end justify-between">
        <div>
          <h1 className="font-display text-2xl font-medium">运行统计</h1>
          <p className="mt-0.5 font-data text-[11px] uppercase tracking-[0.15em] text-ink-faint">
            monitoring · last 90 days
          </p>
        </div>
        {stats?.profile.updated_at && (
          <p className="font-data text-[11px] text-ink-faint">
            画像更新于 {stats.profile.updated_at.slice(0, 10)}
          </p>
        )}
      </div>

      {!stats && !error && <StatsSkeleton />}

      {error && (
        <div className="rounded-lg border border-line bg-surface p-8 text-center shadow-card">
          <p className="font-display text-lg">暂时无法加载统计数据</p>
          <p className="mt-1 text-sm text-ink-muted">{error}</p>
          <button
            type="button"
            onClick={retry}
            className="mt-4 rounded-md bg-accent px-4 py-2 text-sm text-white transition-colors hover:bg-accent-strong"
          >
            重试
          </button>
        </div>
      )}

      {stats && (
        <div className="space-y-4">
          <StatTiles
            daily={daily}
            production={stats.models.production}
            interactionCount={stats.profile.interaction_count}
          />

          <ChartCard
            title="点击率走势"
            subtitle="ctr · daily"
            headline={
              hasData
                ? `${(daily[daily.length - 1].ctr * 100).toFixed(1)}%`
                : undefined
            }
          >
            {hasData ? (
              <CtrChart daily={daily} />
            ) : (
              <EmptyChart hint="metrics_rollup 每日汇总后,这里会出现近 90 天的 CTR 曲线" />
            )}
          </ChartCard>

          <ChartCard title="互动量" subtitle="impressions / clicks / saves · last 14 days">
            {hasData ? (
              <EngagementChart daily={daily} />
            ) : (
              <EmptyChart hint="开始刷信息流后,每日曝光与互动会汇总到这里" />
            )}
          </ChartCard>

          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard
              title="画像漂移"
              subtitle="profile drift · cos distance vs 30d ago"
              headline={
                hasData &&
                typeof daily[daily.length - 1].profile_drift === "number"
                  ? daily[daily.length - 1].profile_drift!.toFixed(3)
                  : undefined
              }
            >
              {hasData ? (
                <DriftChart daily={daily} />
              ) : (
                <EmptyChart hint="画像每日重算后,兴趣漂移曲线会出现在这里" />
              )}
            </ChartCard>

            <ChartCard title="模型版本时间线" subtitle="model registry · rollouts">
              <ModelTimeline
                daily={daily}
                production={stats.models.production}
                staging={stats.models.staging}
              />
            </ChartCard>
          </div>
        </div>
      )}
    </div>
  );
}
