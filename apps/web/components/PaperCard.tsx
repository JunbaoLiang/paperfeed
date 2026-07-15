"use client";

import { useState } from "react";
import type { FeedItem } from "@/lib/types";
import { tracker } from "@/lib/tracker";
import { useImpressionTracking } from "@/lib/useImpressionTracking";
import {
  CategoryBadges,
  ReasonKicker,
  formatAuthors,
  formatDate,
  pdfHref,
} from "@/components/paper-bits";
import { BookmarkIcon, DismissIcon, PdfIcon } from "@/components/icons";

interface Props {
  item: FeedItem;
  index: number;
  onRemoved: (impressionId: string) => void;
}

const DISMISS_ANIM_MS = 420;

export default function PaperCard({ item, index, onRemoved }: Props) {
  const { impression_id, paper, position, recall_source, reason } = item;
  const { ref, onExpandChange } = useImpressionTracking(impression_id);

  const [expanded, setExpanded] = useState(false);
  const [saved, setSaved] = useState(false);
  const [dismissing, setDismissing] = useState(false);

  const toggleAbstract = () => {
    const next = !expanded;
    setExpanded(next);
    onExpandChange(next);
  };

  const handleSave = () => {
    setSaved((s) => !s);
    // The tracker dedupes, so toggling off/on never double-sends `save`.
    tracker.track(impression_id, "save");
  };

  const handleDismiss = () => {
    if (dismissing) return;
    tracker.track(impression_id, "dismiss");
    setDismissing(true);
    setTimeout(() => onRemoved(impression_id), DISMISS_ANIM_MS);
  };

  const handlePdf = () => {
    tracker.track(impression_id, "click_pdf");
  };

  return (
    <div className={`dismiss-wrap ${dismissing ? "dismissing" : ""}`}>
      <div className="overflow-hidden">
        <article
          ref={ref as React.Ref<HTMLElement>}
          className="card-enter mb-4 rounded-lg border border-line bg-surface p-4 shadow-card sm:p-5"
          style={{ animationDelay: `${Math.min(index, 8) * 60}ms` }}
        >
          {/* meta row */}
          <div className="mb-2 flex items-baseline justify-between gap-3 font-data text-[11px] text-ink-faint">
            <span>
              <span className="text-accent">{String(position).padStart(2, "0")}</span>
              {" · "}
              <a
                href={`https://arxiv.org/abs/${paper.arxiv_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-ink-muted transition-colors"
              >
                arXiv:{paper.arxiv_id}
              </a>
            </span>
            <span className="shrink-0">
              {formatDate(paper.published_at)}
              {typeof paper.citation_count === "number" &&
                ` · 被引 ${paper.citation_count}`}
            </span>
          </div>

          <ReasonKicker source={recall_source} reason={reason} />

          <h2 className="mt-1.5 font-display text-lg font-medium leading-snug sm:text-xl">
            {paper.title}
          </h2>

          <p className="mt-1 text-sm text-ink-muted">{formatAuthors(paper)}</p>

          <div className="mt-2.5">
            <CategoryBadges paper={paper} />
          </div>

          {/* abstract: collapsed to 3 lines; expanding fires click_abstract */}
          <div
            role="button"
            tabIndex={0}
            aria-expanded={expanded}
            onClick={toggleAbstract}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                toggleAbstract();
              }
            }}
            className="group mt-3 cursor-pointer select-text"
          >
            <p
              className={`text-[0.925rem] leading-relaxed text-ink/90 ${
                expanded ? "" : "clamp-3"
              }`}
            >
              {paper.abstract}
            </p>
            <span className="mt-1 inline-block text-xs text-accent group-hover:text-accent-strong">
              {expanded ? "收起 ▴" : "展开摘要 ▾"}
            </span>
          </div>

          {/* actions */}
          <div className="mt-4 flex items-center gap-2 border-t border-line pt-3">
            <button
              type="button"
              onClick={handleSave}
              aria-pressed={saved}
              className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm transition-all active:scale-95 ${
                saved
                  ? "border-gold/40 bg-gold-soft text-gold"
                  : "border-line text-ink-muted hover:border-line-strong hover:text-ink"
              }`}
            >
              <BookmarkIcon className="h-4 w-4" filled={saved} />
              {saved ? "已收藏" : "收藏"}
            </button>
            <button
              type="button"
              onClick={handleDismiss}
              className="flex items-center gap-1.5 rounded-md border border-line px-3 py-1.5 text-sm text-ink-muted transition-all hover:border-line-strong hover:text-ink active:scale-95"
            >
              <DismissIcon className="h-4 w-4" />
              不感兴趣
            </button>
            <a
              href={pdfHref(paper)}
              target="_blank"
              rel="noopener noreferrer"
              onClick={handlePdf}
              className="ml-auto flex items-center gap-1.5 rounded-md px-3 py-1.5 font-data text-sm text-accent transition-colors hover:bg-accent-soft"
            >
              <PdfIcon className="h-4 w-4" />
              PDF
            </a>
          </div>
        </article>
      </div>
    </div>
  );
}
