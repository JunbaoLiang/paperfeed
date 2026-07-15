"use client";

import Link from "next/link";
import { ArrowRightIcon, DismissIcon } from "@/components/icons";

/**
 * Cold-start banner shown on the feed while interaction_count < 10.
 * Dismissal persists in localStorage.
 */
export default function OnboardingBanner({
  onDismiss,
}: {
  onDismiss: () => void;
}) {
  return (
    <div className="card-enter mb-4 flex items-center gap-3 rounded-lg border border-accent/25 bg-accent-soft px-4 py-3">
      <div className="min-w-0 flex-1 text-sm">
        <span className="text-ink">推荐还在冷启动阶段 — </span>
        <Link
          href="/onboarding"
          className="inline-flex items-center gap-1 font-medium text-accent underline-offset-2 hover:underline"
        >
          完成引导以获得个性化推荐
          <ArrowRightIcon className="h-3.5 w-3.5" />
        </Link>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="关闭提示"
        className="shrink-0 rounded p-1 text-ink-muted transition-colors hover:text-ink"
      >
        <DismissIcon className="h-4 w-4" />
      </button>
    </div>
  );
}
