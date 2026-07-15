"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "信息流", en: "Feed" },
  { href: "/saved", label: "收藏", en: "Saved" },
  { href: "/stats", label: "统计", en: "Stats" },
] as const;

export default function NavBar() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 bg-paper/90 backdrop-blur-sm">
      <div className="mx-auto max-w-5xl px-4">
        <div className="flex items-baseline justify-between pt-4 pb-2">
          <Link href="/" className="group flex items-baseline gap-2">
            <span className="font-display italic text-2xl sm:text-[1.7rem] font-medium tracking-tight leading-none">
              PaperFeed<span className="text-accent not-italic">.</span>
            </span>
            <span className="hidden sm:inline font-data text-[10px] uppercase tracking-[0.18em] text-ink-faint group-hover:text-ink-muted transition-colors">
              arXiv · daily
            </span>
          </Link>
          <nav className="flex items-baseline gap-1" aria-label="主导航">
            {TABS.map((tab) => {
              const active =
                tab.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(tab.href);
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  aria-current={active ? "page" : undefined}
                  className={`relative px-3 py-1.5 text-sm transition-colors ${
                    active
                      ? "text-ink font-medium"
                      : "text-ink-muted hover:text-ink"
                  }`}
                >
                  {tab.label}
                  <span
                    className={`absolute left-3 right-3 -bottom-[9px] h-[2px] rounded-full transition-all ${
                      active ? "bg-accent" : "bg-transparent"
                    }`}
                  />
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
      <div className="double-rule" />
    </header>
  );
}
