"use client";

// DSH-6, owner: A. Q&A box wired to POST /qa (KNW-2): truth-state-labeled,
// cited answers. Sources render below the answer — the citations ARE the product.
import { useState } from "react";
import { api } from "@/lib/api-client";
import { personaFromDocument } from "@/lib/persona-client";
import type { QAResponse } from "@/lib/types";

const SUGGESTED = [
  "Vì sao đổi sang đèn LED thay vì lồng đèn giấy?",
  "Chủ nhật 20/9 có lớp không? Lịch học chung có đổi không?",
  "Ngân sách đêm hội trần bao nhiêu, vượt thì ai duyệt?",
];

export default function QAPage() {
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QAResponse | null>(null);
  const [showSources, setShowSources] = useState(false);

  async function ask(q: string) {
    if (!q.trim() || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.askQA(q, personaFromDocument()));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl">
      <h1 className="mb-1 text-lg font-semibold">Ask EverMind</h1>
      <p className="mb-4 text-sm text-slate-500">
        Hỏi bộ nhớ tổ chức — trả lời kèm trích dẫn [D#]/[T#]/[m#], phân biệt quyết định
        còn hiệu lực / đã thay thế / đang chờ duyệt.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
        className="flex gap-2"
      >
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ví dụ: Ngân sách đêm hội trần bao nhiêu?"
          className="flex-1 rounded-md border border-slate-200 px-3 py-2 text-sm dark:border-slate-800 dark:bg-transparent"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-brand-coral px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? "Đang tìm…" : "Hỏi"}
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTED.map((q) => (
          <button
            key={q}
            onClick={() => {
              setQuestion(q);
              ask(q);
            }}
            disabled={busy}
            className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 hover:border-brand-coral dark:border-slate-800 dark:text-slate-300"
          >
            {q}
          </button>
        ))}
      </div>

      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}

      {result && (
        <div className="mt-6 space-y-3">
          <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
            <p className="whitespace-pre-wrap text-sm">{result.answer}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {result.cited_decision_ids.map((id) => (
                <span key={`d${id}`} className="rounded bg-emerald-100 px-1.5 py-0.5 text-xs text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                  D{id}
                </span>
              ))}
              {result.cited_task_ids.map((id) => (
                <span key={`t${id}`} className="rounded bg-sky-100 px-1.5 py-0.5 text-xs text-sky-700 dark:bg-sky-950 dark:text-sky-300">
                  T{id}
                </span>
              ))}
              {result.cited_message_ids.map((id) => (
                <span key={`m${id}`} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  m{String(id).padStart(4, "0")}
                </span>
              ))}
            </div>
            {!result.llm && (
              <p className="mt-2 text-xs text-amber-600">
                LLM không khả dụng — hiển thị kết quả truy xuất có cấu trúc.
              </p>
            )}
          </div>

          {result.sources.length > 0 && (
            <div>
              <button
                onClick={() => setShowSources((s) => !s)}
                className="text-xs text-brand-coral hover:underline"
              >
                {showSources ? "Ẩn" : "Xem"} {result.sources.length} nguồn đã truy xuất
              </button>
              {showSources && (
                <ul className="mt-2 space-y-1 rounded-md bg-surface-sunken p-3 text-xs text-slate-600 dark:bg-surface-dark-sunken dark:text-slate-300">
                  {result.sources.map((line, i) => (
                    <li key={i} className="font-mono">{line}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
