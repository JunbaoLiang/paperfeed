"use client";

import { useState } from "react";
import type { SavedItem } from "@/lib/types";
import {
  CategoryBadges,
  absHref,
  formatAuthors,
  formatDate,
  pdfHref,
} from "@/components/paper-bits";
import { BookmarkIcon, PdfIcon } from "@/components/icons";

/** Saved-page card: same editorial style, no event tracking. */
export default function SavedCard({
  item,
  index,
}: {
  item: SavedItem;
  index: number;
}) {
  const { paper, saved_at } = item;
  const [expanded, setExpanded] = useState(false);

  return (
    <article
      className="card-enter mb-4 rounded-lg border border-line bg-surface p-4 shadow-card sm:p-5"
      style={{ animationDelay: `${Math.min(index, 8) * 60}ms` }}
    >
      <div className="mb-2 flex items-baseline justify-between gap-3 font-data text-[11px] text-ink-faint">
        <a
          href={absHref(paper)}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-ink-muted transition-colors"
        >
          arXiv:{paper.arxiv_id}
        </a>
        <span className="flex shrink-0 items-center gap-1 text-gold">
          <BookmarkIcon className="h-3 w-3" filled />
          {formatDate(saved_at)} 收藏
        </span>
      </div>

      <h2 className="font-display text-lg font-medium leading-snug sm:text-xl">
        {paper.title}
      </h2>
      <p className="mt-1 text-sm text-ink-muted">{formatAuthors(paper)}</p>

      <div className="mt-2.5">
        <CategoryBadges paper={paper} />
      </div>

      <div
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        onClick={() => setExpanded((e) => !e)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setExpanded((v) => !v);
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

      <div className="mt-4 flex items-center gap-2 border-t border-line pt-3">
        <a
          href={absHref(paper)}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-md border border-line px-3 py-1.5 font-data text-sm text-ink-muted transition-colors hover:border-line-strong hover:text-ink"
        >
          arXiv ↗
        </a>
        <a
          href={pdfHref(paper)}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto flex items-center gap-1.5 rounded-md px-3 py-1.5 font-data text-sm text-accent transition-colors hover:bg-accent-soft"
        >
          <PdfIcon className="h-4 w-4" />
          PDF
        </a>
      </div>
    </article>
  );
}
