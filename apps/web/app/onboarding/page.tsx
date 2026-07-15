"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowRightIcon,
  CheckIcon,
  DismissIcon,
  VectorIcon,
} from "@/components/icons";

const MIN_KEYWORDS = 3;
const MAX_KEYWORDS = 5;

const SUGGESTIONS = [
  "graph neural networks",
  "large language models",
  "protein folding",
  "reinforcement learning",
  "diffusion models",
  "recommendation systems",
];

export default function OnboardingPage() {
  const [keywords, setKeywords] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addKeyword = (raw: string) => {
    const kw = raw.trim().replace(/,+$/, "");
    if (!kw) return;
    if (keywords.length >= MAX_KEYWORDS) return;
    if (keywords.some((k) => k.toLowerCase() === kw.toLowerCase())) {
      setInput("");
      return;
    }
    setKeywords((prev) => [...prev, kw]);
    setInput("");
  };

  const removeKeyword = (kw: string) => {
    setKeywords((prev) => prev.filter((k) => k !== kw));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addKeyword(input);
    } else if (e.key === "Backspace" && input === "" && keywords.length > 0) {
      setKeywords((prev) => prev.slice(0, -1));
    }
  };

  const submit = async () => {
    if (keywords.length < MIN_KEYWORDS || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/seed-profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keywords }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.error ?? `提交失败(HTTP ${res.status})`);
      }
      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "提交失败,请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className="mx-auto max-w-lg px-4 pt-16 pb-10 text-center">
        <div className="card-enter rounded-lg border border-line bg-surface p-8 shadow-card sm:p-10">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-accent-soft">
            <CheckIcon className="h-7 w-7 text-accent" />
          </span>
          <h1 className="mt-5 font-display text-2xl font-medium">
            兴趣画像已提交
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            个性化推荐将于<span className="text-ink font-medium">明日生效</span>
            —— 离线管道会在夜间将关键词编码为画像向量。
            在此之前,信息流会优先展示今日新发布的高热度论文。
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-1.5">
            {keywords.map((kw) => (
              <span
                key={kw}
                className="rounded-sm bg-accent-soft px-2 py-0.5 font-data text-xs text-accent"
              >
                {kw}
              </span>
            ))}
          </div>
          <Link
            href="/"
            className="mt-7 inline-flex items-center gap-1.5 rounded-md bg-accent px-5 py-2.5 text-sm text-white transition-colors hover:bg-accent-strong"
          >
            返回信息流
            <ArrowRightIcon className="h-4 w-4" />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg px-4 pt-10 pb-10">
      <div className="card-enter rounded-lg border border-line bg-surface p-6 shadow-card sm:p-8">
        <p className="flex items-center gap-1.5 font-data text-[11px] uppercase tracking-[0.15em] text-ink-faint">
          <VectorIcon className="h-3.5 w-3.5 text-accent" />
          cold start · seed profile
        </p>
        <h1 className="mt-2 font-display text-2xl font-medium">
          告诉我你的研究兴趣
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-muted">
          输入 {MIN_KEYWORDS}–{MAX_KEYWORDS} 个关键词(英文,如
          &ldquo;graph neural networks&rdquo;),系统会以此构建初始兴趣画像。
        </p>

        {/* tag input */}
        <div
          className="mt-5 flex min-h-[52px] flex-wrap items-center gap-1.5 rounded-md border border-line bg-paper px-3 py-2 focus-within:border-accent/60"
          onClick={(e) => {
            (e.currentTarget.querySelector("input") as HTMLInputElement)?.focus();
          }}
        >
          {keywords.map((kw) => (
            <span
              key={kw}
              className="flex items-center gap-1 rounded-sm bg-accent-soft py-1 pl-2 pr-1 font-data text-xs text-accent"
            >
              {kw}
              <button
                type="button"
                onClick={() => removeKeyword(kw)}
                aria-label={`移除 ${kw}`}
                className="rounded p-0.5 transition-colors hover:bg-accent/15"
              >
                <DismissIcon className="h-3 w-3" />
              </button>
            </span>
          ))}
          {keywords.length < MAX_KEYWORDS && (
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={() => addKeyword(input)}
              placeholder={
                keywords.length === 0 ? "输入关键词后按回车…" : "继续添加…"
              }
              className="min-w-[140px] flex-1 bg-transparent py-1 text-sm outline-none placeholder:text-ink-faint"
            />
          )}
        </div>
        <p className="mt-1.5 text-right font-data text-[11px] text-ink-faint">
          {keywords.length}/{MAX_KEYWORDS}
        </p>

        {/* suggestions */}
        <p className="mt-3 text-xs text-ink-muted">试试这些方向:</p>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {SUGGESTIONS.filter(
            (s) => !keywords.some((k) => k.toLowerCase() === s.toLowerCase()),
          ).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => addKeyword(s)}
              disabled={keywords.length >= MAX_KEYWORDS}
              className="rounded-sm border border-line px-2 py-1 font-data text-xs text-ink-muted transition-colors hover:border-line-strong hover:text-ink disabled:opacity-40"
            >
              + {s}
            </button>
          ))}
        </div>

        {error && (
          <p className="mt-4 rounded-md border border-accent/25 bg-accent-soft px-3 py-2 text-sm text-accent">
            {error}
          </p>
        )}

        <button
          type="button"
          onClick={submit}
          disabled={keywords.length < MIN_KEYWORDS || submitting}
          className="mt-6 w-full rounded-md bg-accent py-2.5 text-sm font-medium text-white transition-all hover:bg-accent-strong active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting
            ? "提交中…"
            : keywords.length < MIN_KEYWORDS
              ? `至少还需 ${MIN_KEYWORDS - keywords.length} 个关键词`
              : "提交兴趣画像"}
        </button>
      </div>
    </div>
  );
}
