/** Loading placeholders that mirror the paper-card layout. */

export function CardSkeleton() {
  return (
    <div className="mb-4 rounded-lg border border-line bg-surface p-4 shadow-card sm:p-5">
      <div className="mb-3 flex justify-between">
        <div className="skeleton h-3 w-32" />
        <div className="skeleton h-3 w-20" />
      </div>
      <div className="skeleton mb-2 h-3 w-40" />
      <div className="skeleton mb-2 h-5 w-full" />
      <div className="skeleton mb-3 h-5 w-3/4" />
      <div className="skeleton mb-3 h-3 w-48" />
      <div className="mb-3 flex gap-1.5">
        <div className="skeleton h-4 w-14" />
        <div className="skeleton h-4 w-14" />
      </div>
      <div className="skeleton mb-1.5 h-3.5 w-full" />
      <div className="skeleton mb-1.5 h-3.5 w-full" />
      <div className="skeleton mb-4 h-3.5 w-2/3" />
      <div className="flex gap-2 border-t border-line pt-3">
        <div className="skeleton h-8 w-20" />
        <div className="skeleton h-8 w-24" />
        <div className="skeleton ml-auto h-8 w-16" />
      </div>
    </div>
  );
}

export function FeedSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div aria-busy="true" aria-label="加载中">
      {Array.from({ length: count }, (_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}
