"use client";

// Evidence receipt modal, ⌘K search palette, Ask EverMind (QA) modal —
// ported from frontend_ref, fed by live data.
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api-client";
import { personaFromDocument } from "@/lib/persona-client";
import type { QAResponse } from "@/lib/types";
import {
  ORG_TZ, WsBundle, WsEvidence, avatarClass, decisionLabel, initials,
  messageLabel, statusLabel, taskLabel,
} from "@/lib/workspace";
import { Icon } from "./icons";

const sourceName = (s: string) => (s === "transcript" ? "Transcript" : s === "telegram" ? "Telegram" : "Chat");

export function EvidenceModal({
  item, bundle, onClose, onOpenTask, onOpenDecision,
}: {
  item: WsEvidence;
  bundle: WsBundle;
  onClose: () => void;
  onOpenTask: (id: number) => void;
  onOpenDecision: (id: number) => void;
}) {
  const member = bundle.members.find((m) => m.id === item.author_user_id);
  const name = member?.name ?? item.author_identity;
  return (
    <div className="modal-shell open" aria-hidden="false">
      <button className="overlay-backdrop" aria-label="Đóng evidence" onClick={onClose} />
      <section className="evidence-modal" role="dialog" aria-modal="true">
        <div>
          <div className="modal-head">
            <div>
              <span className="modal-head-label">Evidence receipt</span>
              <h2>{messageLabel(item.message_id)} · {sourceName(item.source)}</h2>
            </div>
            <button className="icon-button modal-close" aria-label="Đóng" onClick={onClose}>
              <Icon name="close" />
            </button>
          </div>
          <div className="modal-body">
            <div className="receipt-proof">
              <div className="proof-meta">
                <span className="proof-author">
                  <span className={`avatar ${avatarClass(item.author_user_id)}`}>{initials(name)}</span>
                  {name}
                </span>
                <span>{new Date(item.ts).toLocaleString("vi-VN", { timeZone: ORG_TZ })} · {item.channel ?? item.source}</span>
              </div>
              <blockquote>“{item.text}”</blockquote>
              <div className="proof-context">
                {item.thread_ref != null
                  ? `Reply → ${messageLabel(item.thread_ref)} · `
                  : ""}
                Captured verbatim · immutable revision
              </div>
            </div>
            <div className="receipt-fields">
              <div className="receipt-field"><span>Pinned revision</span><strong>rev {item.rev}</strong></div>
              <div className="receipt-field"><span>Source</span><strong>{sourceName(item.source)}</strong></div>
              <div className="receipt-field"><span>Source locator</span><strong>{item.channel ?? "-"}:{messageLabel(item.message_id)}</strong></div>
              <div className="receipt-field"><span>Provenance ref</span><strong>{item.raw_ref}</strong></div>
            </div>
            <h3 className="backlink-heading">Backlinks · used by {item.backlinks.length} records</h3>
            {item.backlinks.map((link, i) => (
              <div
                key={i}
                className="backlink-row"
                role="button"
                tabIndex={0}
                onClick={() => {
                  onClose();
                  if (link.type === "decision") onOpenDecision(link.id);
                  else onOpenTask(link.id);
                }}
              >
                <Icon name={link.type} />
                <div>
                  <strong>{link.type === "decision" ? decisionLabel(link.id) : taskLabel(link.id)}</strong>
                  <small>{link.label} · {link.role}</small>
                </div>
                <Icon name="chevron" />
              </div>
            ))}
          </div>
          <div className="modal-actions">
            <button className="secondary-button" onClick={onClose}>Close</button>
          </div>
        </div>
      </section>
    </div>
  );
}

interface SearchItem {
  type: "task" | "decision" | "evidence";
  id: number;
  title: string;
  detail: string;
  haystack: string;
}

export function SearchPalette({
  bundle, initialQuery, onClose, onOpenTask, onOpenDecision, onOpenEvidence,
}: {
  bundle: WsBundle;
  initialQuery?: string;
  onClose: () => void;
  onOpenTask: (id: number) => void;
  onOpenDecision: (id: number) => void;
  onOpenEvidence: (id: number) => void;
}) {
  const [query, setQuery] = useState(initialQuery ?? "");

  const items = useMemo<SearchItem[]>(() => [
    ...bundle.tasks.map((t) => ({
      type: "task" as const, id: t.id, title: t.description,
      detail: `${statusLabel(t.status)} · ${t.decision_ids.length} decisions`,
      haystack: `${taskLabel(t.id)} ${t.description} ${Object.values(t.facts).join(" ")}`,
    })),
    ...bundle.decisions.map((d) => ({
      type: "decision" as const, id: d.id, title: d.description,
      detail: `${d.status} · @${d.decided_by_handle ?? d.decided_by_user_id}`,
      haystack: `${decisionLabel(d.id)} ${d.description} ${d.context ?? ""} ${d.note ?? ""}`,
    })),
    ...bundle.evidence.map((e) => ({
      type: "evidence" as const, id: e.message_id, title: e.text,
      detail: `${sourceName(e.source)} · @${e.author_identity}`,
      haystack: `${messageLabel(e.message_id)} ${e.text} ${e.author_identity}`,
    })),
  ], [bundle]);

  const q = query.trim().toLowerCase();
  const results = items.filter((it) => !q || it.haystack.toLowerCase().includes(q)).slice(0, 9);
  const grouped = results.reduce<Record<string, SearchItem[]>>((acc, it) => {
    (acc[it.type] ||= []).push(it);
    return acc;
  }, {});

  const choose = (item: SearchItem) => {
    onClose();
    if (item.type === "task") onOpenTask(item.id);
    if (item.type === "decision") onOpenDecision(item.id);
    if (item.type === "evidence") onOpenEvidence(item.id);
  };

  return (
    <div className="search-overlay open" aria-hidden="false">
      <button className="overlay-backdrop" aria-label="Đóng tìm kiếm" onClick={onClose} />
      <section className="command-palette" role="dialog" aria-modal="true">
        <div className="command-input-row">
          <Icon name="search" />
          <input
            autoFocus
            type="search"
            placeholder="Tìm task, decision hoặc evidence…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && results[0]) choose(results[0]);
            }}
          />
          <kbd>ESC</kbd>
        </div>
        <div className="search-results">
          {results.length === 0 && (
            <div className="empty-search">
              Không tìm thấy kết quả phù hợp.<br />Thử “LED”, “Kim Long” hoặc “T-02”.
            </div>
          )}
          {Object.entries(grouped).map(([type, list]) => (
            <div key={type}>
              <div className="search-group-label">
                {type === "task" ? "Tasks" : type === "decision" ? "Decisions" : "Evidence"}
              </div>
              {list.map((item, i) => (
                <button
                  key={item.id}
                  className={`search-result ${i === 0 && type === Object.keys(grouped)[0] ? "active" : ""}`}
                  onClick={() => choose(item)}
                >
                  <span className={`search-result-icon ${item.type}`}><Icon name={item.type} /></span>
                  <span className="search-result-copy">
                    <strong>
                      {item.type === "task" ? taskLabel(item.id)
                        : item.type === "decision" ? decisionLabel(item.id)
                          : messageLabel(item.id)} · {item.title}
                    </strong>
                    <small>{item.detail}</small>
                  </span>
                  <span className="search-result-kind">{item.type}</span>
                </button>
              ))}
            </div>
          ))}
        </div>
        <div className="command-footer">
          <span><kbd>↵</kbd> để mở</span>
          <span className="semantic-search"><i></i> Exact search · live projections</span>
        </div>
      </section>
    </div>
  );
}

const SUGGESTIONS = [
  "Vì sao đổi sang đèn LED?",
  "Task nào đang bị chặn và chờ ai?",
  "Ngân sách của dự án là bao nhiêu?",
];

export function AskModal({
  onClose, onOpenTask, onOpenDecision, onOpenEvidence,
}: {
  onClose: () => void;
  onOpenTask: (id: number) => void;
  onOpenDecision: (id: number) => void;
  onOpenEvidence: (id: number) => void;
}) {
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<QAResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function ask(q: string) {
    if (!q.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.askQA(q, personaFromDocument()));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-shell open" aria-hidden="false">
      <button className="overlay-backdrop" aria-label="Đóng" onClick={onClose} />
      <section className="evidence-modal" role="dialog" aria-modal="true">
        <div>
          <div className="modal-head">
            <div>
              <span className="modal-head-label">Ask EverMind</span>
              <h2>Hỏi bộ nhớ tổ chức</h2>
            </div>
            <button className="icon-button modal-close" aria-label="Đóng" onClick={onClose}>
              <Icon name="close" />
            </button>
          </div>
          <div className="modal-body">
            <form
              className="ask-form"
              onSubmit={(e) => {
                e.preventDefault();
                ask(question);
              }}
            >
              <input
                autoFocus
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ví dụ: Vì sao đổi sang đèn LED?"
              />
              <button className="primary-button" type="submit" disabled={busy}>
                {busy ? "Đang trả lời…" : "Hỏi"}
              </button>
            </form>
            <div className="ask-suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => { setQuestion(s); ask(s); }}>{s}</button>
              ))}
            </div>
            {error && <span className="write-note">{error}</span>}
            {result && (
              <>
                <div className="ask-answer">{result.answer}</div>
                {!result.llm && result.sources.length > 0 && (
                  <span className="ask-fallback">
                    LLM không khả dụng — trả về dữ liệu có trích dẫn (structured fallback).
                  </span>
                )}
                <div className="ask-citations">
                  {result.cited_decision_ids.map((id) => (
                    <button key={`d${id}`} onClick={() => { onClose(); onOpenDecision(id); }}>
                      {decisionLabel(id)}
                    </button>
                  ))}
                  {result.cited_task_ids.map((id) => (
                    <button key={`t${id}`} onClick={() => { onClose(); onOpenTask(id); }}>
                      {taskLabel(id)}
                    </button>
                  ))}
                  {result.cited_message_ids.map((id) => (
                    <button key={`m${id}`} onClick={() => { onClose(); onOpenEvidence(id); }}>
                      {messageLabel(id)}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
          <div className="modal-actions">
            <button className="secondary-button" onClick={onClose}>Close</button>
          </div>
        </div>
      </section>
    </div>
  );
}
