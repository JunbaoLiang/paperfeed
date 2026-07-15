"use client";

import { useCallback, useEffect, useState } from "react";
import type { FeedItem, FeedResponse, StatsResponse } from "@/lib/types";
import { tracker } from "@/lib/tracker";
import PaperCard from "@/components/PaperCard";
import OnboardingBanner from "@/components/OnboardingBanner";
import { FeedSkeleton } from "@/components/Skeletons";
import { RefreshIcon } from "@/components/icons";

const BANNER_DISMISS_KEY = "pf-onboarding-banner-dismissed";

export default function FeedPage() {
  const [items, setItems] = useState<FeedItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showBanner, setShowBanner] = useState(false);

  // State updates happen inside promise callbacks (never synchronously in
  // an effect body) — callers set loading/error before invoking.
  const doFetch = useCallback(() => {
    // Flush anything pending (incl. dwells recorded as old cards unmount).
    tracker.flush();
    fetch("/api/feed?n=20")
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.error ?? `请求失败(HTTP ${res.status})`);
        }
        return res.json() as Promise<FeedResponse>;
      })
      .then((data) => {
        setItems(data.items);
        setError(null);
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "加载失败,请稍后重试");
        setItems(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const fetchFeed = useCallback(() => {
    setLoading(true);
    setError(null);
    doFetch();
  }, [doFetch]);

  useEffect(() => {
    tracker.start();
    doFetch(); // initial state is already loading=true

    // Cold-start banner: only while interaction_count < 10 and not dismissed.
    if (window.localStorage.getItem(BANNER_DISMISS_KEY) !== "1") {
      fetch("/api/stats")
        .then((r) => (r.ok ? (r.json() as Promise<StatsResponse>) : null))
        .then((stats) => {
          if (stats && stats.profile.interaction_count < 10) {
            setShowBanner(true);
          }
        })
        .catch(() => {});
    }
  }, [doFetch]);

  const removeItem = useCallback((impressionId: string) => {
    setItems(
      (prev) => prev?.filter((i) => i.impression_id !== impressionId) ?? prev,
    );
  }, []);

  const dismissBanner = useCallback(() => {
    setShowBanner(false);
    window.localStorage.setItem(BANNER_DISMISS_KEY, "1");
  }, []);

  return (
    <div className="mx-auto max-w-2xl px-4 pt-6 pb-10">
      <div className="mb-5 flex items-end justify-between">
        <div>
          <h1 className="font-display text-2xl font-medium">今日推荐</h1>
          <p className="mt-0.5 font-data text-[11px] uppercase tracking-[0.15em] text-ink-faint">
            recall → rank → rerank
          </p>
        </div>
        <button
          type="button"
          onClick={fetchFeed}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-md border border-line bg-surface px-3 py-1.5 text-sm text-ink-muted shadow-card transition-all hover:border-line-strong hover:text-ink active:scale-95 disabled:opacity-50"
        >
          <RefreshIcon className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          刷新推荐
        </button>
      </div>

      {showBanner && <OnboardingBanner onDismiss={dismissBanner} />}

      {loading && <FeedSkeleton count={4} />}

      {!loading && error && (
        <div className="rounded-lg border border-line bg-surface p-8 text-center shadow-card">
          <p className="font-display text-lg">暂时无法加载推荐</p>
          <p className="mt-1 text-sm text-ink-muted">{error}</p>
          <button
            type="button"
            onClick={fetchFeed}
            className="mt-4 rounded-md bg-accent px-4 py-2 text-sm text-white transition-colors hover:bg-accent-strong"
          >
            重试
          </button>
        </div>
      )}

      {!loading && !error && items && items.length === 0 && (
        <div className="rounded-lg border border-line bg-surface p-8 text-center shadow-card">
          <p className="font-display text-lg">今天没有更多推荐了</p>
          <p className="mt-1 text-sm text-ink-muted">
            数据管道每日抓取新论文,明天再来看看。
          </p>
        </div>
      )}

      {!loading && !error && items && items.length > 0 && (
        <section aria-label="推荐论文列表">
          {items.map((item, i) => (
            <PaperCard
              key={item.impression_id}
              item={item}
              index={i}
              onRemoved={removeItem}
            />
          ))}
          <p className="pt-2 text-center font-data text-[11px] text-ink-faint">
            — 本次推荐到此为止 · 点击「刷新推荐」获取新一批 —
          </p>
        </section>
      )}
    </div>
  );
}
