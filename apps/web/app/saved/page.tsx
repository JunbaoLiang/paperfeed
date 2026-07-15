"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { SavedItem, SavedResponse } from "@/lib/types";
import SavedCard from "@/components/SavedCard";
import { FeedSkeleton } from "@/components/Skeletons";
import { BookmarkIcon } from "@/components/icons";

export default function SavedPage() {
  const [items, setItems] = useState<SavedItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/saved")
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.error ?? `请求失败(HTTP ${res.status})`);
        }
        return res.json() as Promise<SavedResponse>;
      })
      .then((data) => setItems(data.items))
      .catch((e) =>
        setError(e instanceof Error ? e.message : "加载失败,请稍后重试"),
      );
  }, []);

  const loading = items === null && error === null;

  return (
    <div className="mx-auto max-w-2xl px-4 pt-6 pb-10">
      <div className="mb-5">
        <h1 className="font-display text-2xl font-medium">我的收藏</h1>
        <p className="mt-0.5 font-data text-[11px] uppercase tracking-[0.15em] text-ink-faint">
          saved papers
        </p>
      </div>

      {loading && <FeedSkeleton count={3} />}

      {error && (
        <div className="rounded-lg border border-line bg-surface p-8 text-center shadow-card">
          <p className="font-display text-lg">暂时无法加载收藏</p>
          <p className="mt-1 text-sm text-ink-muted">{error}</p>
        </div>
      )}

      {items && items.length === 0 && (
        <div className="rounded-lg border border-line bg-surface p-10 text-center shadow-card">
          <BookmarkIcon className="mx-auto h-8 w-8 text-ink-faint" />
          <p className="mt-3 font-display text-lg">还没有收藏任何论文</p>
          <p className="mt-1 text-sm text-ink-muted">
            在信息流中点击「收藏」,论文会出现在这里。
          </p>
          <Link
            href="/"
            className="mt-4 inline-block rounded-md bg-accent px-4 py-2 text-sm text-white transition-colors hover:bg-accent-strong"
          >
            去逛信息流
          </Link>
        </div>
      )}

      {items && items.length > 0 && (
        <section aria-label="收藏列表">
          {items.map((item, i) => (
            <SavedCard key={item.paper.arxiv_id} item={item} index={i} />
          ))}
        </section>
      )}
    </div>
  );
}
