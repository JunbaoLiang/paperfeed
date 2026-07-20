"use client";

import { useState } from "react";

interface ExternalReadResult {
  status: "recorded" | "pending_embedding" | "already_recorded";
  arxiv_id: string;
  title: string;
}

const STATUS_TEXT: Record<ExternalReadResult["status"], string> = {
  recorded: "已记录,将计入你的兴趣画像",
  pending_embedding: "已记录,论文向量化后生效(明日)",
  already_recorded: "这篇之前已经记录过了",
};

/**
 * 记录在站外读过的论文(spec v1.2):粘贴 arXiv 链接或 ID,
 * 作为最强正反馈进入画像与训练数据。
 */
export default function ExternalReadForm() {
  const [ref, setRef] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(
    null,
  );

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!ref.trim() || busy) return;
    setBusy(true);
    setMessage(null);
    try {
      const res = await fetch("/api/external-read", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ref: ref.trim() }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        const detail =
          body?.detail ?? body?.error ?? `请求失败(HTTP ${res.status})`;
        throw new Error(
          typeof detail === "string" ? detail : "无法识别这个链接",
        );
      }
      const result = body as ExternalReadResult;
      setMessage({
        ok: true,
        text: `《${result.title}》— ${STATUS_TEXT[result.status]}`,
      });
      setRef("");
    } catch (err) {
      setMessage({
        ok: false,
        text: err instanceof Error ? err.message : "提交失败,请稍后重试",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mb-6 rounded-lg border border-line bg-surface p-4 shadow-card">
      <p className="font-display text-sm font-medium">记录站外读过的论文</p>
      <p className="mt-0.5 text-xs text-ink-muted">
        在别处读到好论文?粘贴 arXiv 链接 / DOI /
        含 DOI 的期刊链接,它会作为强正反馈进入你的兴趣画像和训练数据。
      </p>
      <form onSubmit={submit} className="mt-3 flex gap-2">
        <input
          type="text"
          value={ref}
          onChange={(e) => setRef(e.target.value)}
          placeholder="arXiv 链接 / 2501.12345 / 10.1021/jacs.xxxxx"
          className="min-w-0 flex-1 rounded-md border border-line bg-page px-3 py-2 text-sm outline-none transition-colors focus:border-accent"
          disabled={busy}
          aria-label="arXiv 链接或 ID"
        />
        <button
          type="submit"
          disabled={busy || !ref.trim()}
          className="shrink-0 rounded-md bg-accent px-4 py-2 text-sm text-white transition-colors hover:bg-accent-strong disabled:opacity-50"
        >
          {busy ? "记录中…" : "记录"}
        </button>
      </form>
      {message && (
        <p
          className={`mt-2 text-xs ${message.ok ? "text-ink-muted" : "text-accent-strong"}`}
          role="status"
        >
          {message.text}
        </p>
      )}
    </div>
  );
}
