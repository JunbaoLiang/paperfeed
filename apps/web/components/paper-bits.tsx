import type { Paper, RecallSource } from "@/lib/types";
import {
  ExploreIcon,
  FreshIcon,
  GraphIcon,
  VectorIcon,
} from "@/components/icons";

/** "First 3 authors + et al." */
export function formatAuthors(paper: Paper, max = 3): string {
  const names = paper.authors.map((a) => a.name).filter(Boolean);
  if (names.length === 0) return "—";
  if (names.length <= max) return names.join(", ");
  return `${names.slice(0, max).join(", ")} et al.`;
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function pdfHref(paper: Paper): string {
  return paper.pdf_url ?? `https://arxiv.org/pdf/${paper.arxiv_id}`;
}

export function absHref(paper: Paper): string {
  return `https://arxiv.org/abs/${paper.arxiv_id}`;
}

export function CategoryBadges({ paper }: { paper: Paper }) {
  // Primary category first, highlighted; cap the rest to keep one line tidy.
  const rest = paper.categories
    .filter((c) => c !== paper.primary_category)
    .slice(0, 3);
  return (
    <div className="rail flex gap-1.5 overflow-x-auto">
      <span className="shrink-0 rounded-sm bg-accent-soft px-1.5 py-0.5 font-data text-[10px] tracking-wide text-accent">
        {paper.primary_category}
      </span>
      {rest.map((cat) => (
        <span
          key={cat}
          className="shrink-0 rounded-sm border border-line px-1.5 py-0.5 font-data text-[10px] tracking-wide text-ink-faint"
        >
          {cat}
        </span>
      ))}
    </div>
  );
}

const REASON_META: Record<
  RecallSource,
  { Icon: (p: { className?: string }) => React.ReactNode; label: string }
> = {
  vector: { Icon: VectorIcon, label: "相似推荐" },
  graph: { Icon: GraphIcon, label: "引文关联" },
  fresh: { Icon: FreshIcon, label: "今日新发布" },
  explore: { Icon: ExploreIcon, label: "探索推荐" },
};

/** Small "kicker" line above the title: recall-source icon + reason text. */
export function ReasonKicker({
  source,
  reason,
}: {
  source: RecallSource;
  reason: string;
}) {
  const meta = REASON_META[source] ?? REASON_META.explore;
  return (
    <p className="flex items-center gap-1.5 text-xs text-ink-muted">
      <meta.Icon className="h-3.5 w-3.5 shrink-0 text-accent" />
      <span className="truncate">{reason || meta.label}</span>
    </p>
  );
}
