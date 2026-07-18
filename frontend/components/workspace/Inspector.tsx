"use client";

// Right-hand inspector: task state / decision lineage / evidence receipts,
// ported from frontend_ref — plus the live write lanes (task status change,
// approve/reject a proposed decision) through POST /commands.
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import { personaFromDocument } from "@/lib/persona-client";
import type { Decision } from "@/lib/types";
import {
  WsBundle, WsEvidence, WsTask, decisionFacet, decisionLabel,
  decisionTaskIds, messageLabel, shortDate, statusLabel, taskLabel,
} from "@/lib/workspace";
import { Icon } from "./icons";

const STATUS_CHOICES = ["todo", "doing", "blocked", "done"];

interface Common {
  bundle: WsBundle;
  showInactive: boolean;
  onToggleInactive: (v: boolean) => void;
  onOpenTask: (id: number) => void;
  onOpenDecision: (id: number) => void;
  onOpenEvidence: (id: number) => void;
  onCloseDecision: () => void;
}

function personaUserId(bundle: WsBundle): number | undefined {
  const handle = personaFromDocument();
  return bundle.members.find((m) => m.handle === handle)?.id;
}

function memberName(bundle: WsBundle, userId: number | null | undefined): string {
  return bundle.members.find((m) => m.id === userId)?.name ?? `user #${userId}`;
}

function ReceiptCard({ item, onOpen }: { item: WsEvidence; onOpen: (id: number) => void }) {
  const role = item.backlinks[0]?.role ?? "evidence";
  return (
    <button className="receipt-card" onClick={() => onOpen(item.message_id)}>
      <span className={`receipt-source ${item.source === "transcript" ? "transcript" : ""}`}>
        <Icon name={item.source === "transcript" ? "evidence" : "telegram"} />
      </span>
      <span className="receipt-copy">
        <strong>
          <span>{messageLabel(item.message_id)} · {item.source === "transcript" ? "Transcript" : "Chat"}</span>
          <span>{shortDate(item.ts)}</span>
        </strong>
        <p>“{item.text.length > 140 ? `${item.text.slice(0, 137)}…` : item.text}”</p>
        <span className="receipt-role">{role}</span>
      </span>
    </button>
  );
}

function DecisionCard({ d, onOpen }: { d: Decision; onOpen: (id: number) => void }) {
  const statusText = d.status.charAt(0).toUpperCase() + d.status.slice(1);
  const relation = d.supersedes_decision_id
    ? `Supersedes ${decisionLabel(d.supersedes_decision_id)}`
    : d.superseded_by_decision_id
      ? `Replaced by ${decisionLabel(d.superseded_by_decision_id)}`
      : decisionFacet(d);
  return (
    <article
      className={`decision-card ${d.status === "superseded" ? "inactive" : ""}`}
      role="button"
      tabIndex={0}
      onClick={() => onOpen(d.id)}
      onKeyDown={(e) => e.key === "Enter" && onOpen(d.id)}
    >
      <div className="decision-card-top">
        <span className="decision-card-id">{decisionLabel(d.id)}</span>
        <span className={`decision-status ${d.status}`}><i></i>{statusText}</span>
      </div>
      <h4>{d.description}</h4>
      <p>{relation}</p>
      <div className="decision-card-meta">
        <span><Icon name="user" />@{d.decided_by_handle ?? d.decided_by_user_id}</span>
        <span><Icon name="clock" />{shortDate(d.ts)}</span>
        <span><Icon name="evidence" />{d.citations.length}</span>
      </div>
    </article>
  );
}

export function TaskInspector({
  task, bundle, showInactive, onToggleInactive, onOpenTask, onOpenDecision, onOpenEvidence,
}: Common & { task: WsTask }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const lineage = bundle.decisions.filter((d) => decisionTaskIds(d).includes(task.id));
  const visible = showInactive ? lineage : lineage.filter((d) => d.status !== "superseded" && d.status !== "rejected");
  const decisionIdSet = new Set(lineage.map((d) => d.id));
  const receipts = bundle.evidence
    .filter((e) => e.backlinks.some(
      (b) => (b.type === "task" && b.id === task.id) || (b.type === "decision" && decisionIdSet.has(b.id)),
    ))
    .slice(0, 4);
  const team = bundle.teams.find((t) => task.team_ids.includes(t.id));
  const pics = task.pics.map((id) => memberName(bundle, id));

  async function changeStatus(next: string) {
    const uid = personaUserId(bundle);
    if (uid === undefined || next === task.status) return;
    setBusy(true);
    setNote(null);
    try {
      const outcome = await api.recordTaskStatus(personaFromDocument(), uid, task.id, next);
      setNote(outcome.status === "applied" ? null : `→ ${outcome.status} (không phải PIC — cần PIC xác nhận)`);
      router.refresh();
    } catch (err) {
      setNote((err as Error).message.slice(0, 120));
    } finally {
      setBusy(false);
    }
  }

  const facts: [string, string][] = [
    ...Object.entries(task.facts).map(([k, v]) => [k, String(v)] as [string, string]),
    ["PIC", pics.length ? pics.join(", ") : "chưa gán"],
    ["Deadline", shortDate(task.end_date) + (task.end_date_defaulted ? " (mặc định)" : "")],
    ...(task.status === "blocked"
      ? [["Waiting on", task.blocked_waiting_on_text ?? `party #${task.blocked_waiting_on_party_id}`] as [string, string]]
      : []),
    ...(team ? [["Team", team.name] as [string, string]] : []),
  ];

  return (
    <>
      <div className="inspector-head">
        <div className="inspector-head-top">
          <span className="inspector-task-id">{taskLabel(task.id)} · Task</span>
          <div className="inspector-actions">
            <select
              className="inspector-status-select"
              value={task.status}
              disabled={busy}
              onChange={(e) => changeStatus(e.target.value)}
              aria-label={`Đổi trạng thái ${taskLabel(task.id)}`}
            >
              {STATUS_CHOICES.concat(STATUS_CHOICES.includes(task.status) ? [] : [task.status]).map((s) => (
                <option key={s} value={s}>{statusLabel(s)}</option>
              ))}
            </select>
          </div>
        </div>
        <h2>{task.description}</h2>
        <div className="inspector-status-row">
          <span className={`status-badge ${task.status}`}><i></i>{statusLabel(task.status)}</span>
          {team && <span className="source-badge">{team.name}</span>}
          {pics[0] && <span className="source-badge">{pics[0]}</span>}
        </div>
        {note && <span className="write-note">{note}</span>}
      </div>
      <div className="inspector-body">
        <div className="current-state-card">
          <div className="section-kicker">
            Current state
            <span className="verified-label"><Icon name="check" /> grounded</span>
          </div>
          <p>
            {task.note
              ?? (task.status === "blocked"
                ? `Đang chờ ${task.blocked_waiting_on_text ?? "bên ngoài"} từ ${shortDate(task.blocked_since)}.`
                : `${statusLabel(task.status)} · ${lineage.length} decisions · ${task.update_count} updates.`)}
          </p>
          <div className="state-facts">
            {facts.map(([label, value]) => (
              <div className="state-fact" key={label}><span>{label}</span><strong>{value}</strong></div>
            ))}
          </div>
        </div>

        <section className="inspector-section">
          <div className="section-heading-row">
            <h3>Dependencies</h3>
            <small>{task.waits_on.length + task.blocks.length} linked</small>
          </div>
          <div className="dependency-list">
            {task.waits_on.map((dep) => {
              const linked = bundle.tasks.find((t) => t.id === dep.task_id);
              return (
                <button className="dependency-item" key={`w${dep.task_id}`} onClick={() => onOpenTask(dep.task_id)}>
                  <span className="dependency-direction"><Icon name="dependency" /></span>
                  <span className="dependency-copy">
                    <strong>{taskLabel(dep.task_id)} · {linked?.description ?? "task"}</strong>
                    <small>chờ task này xong ({dep.status})</small>
                  </span>
                  <span className={`dependency-state ${linked?.status ?? "todo"}`}></span>
                </button>
              );
            })}
            {task.blocks.map((dep) => {
              const linked = bundle.tasks.find((t) => t.id === dep.task_id);
              return (
                <button className="dependency-item" key={`b${dep.task_id}`} onClick={() => onOpenTask(dep.task_id)}>
                  <span className="dependency-direction"><Icon name="arrow" /></span>
                  <span className="dependency-copy">
                    <strong>{taskLabel(dep.task_id)} · {linked?.description ?? "task"}</strong>
                    <small>bị task này chặn ({dep.status})</small>
                  </span>
                  <span className={`dependency-state ${linked?.status ?? "todo"}`}></span>
                </button>
              );
            })}
            {task.waits_on.length + task.blocks.length === 0 && (
              <div className="dependency-item">
                <div className="dependency-direction">✓</div>
                <div className="dependency-copy">
                  <strong>No blocking dependency</strong>
                  <small>This task can progress independently</small>
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="inspector-section">
          <div className="section-heading-row">
            <h3>Decision lineage</h3>
            <label className="toggle-label">
              Show inactive
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(e) => onToggleInactive(e.target.checked)}
              />
              <span className="toggle"></span>
            </label>
          </div>
          <div className="decision-timeline">
            {visible.length
              ? visible.map((d) => <DecisionCard key={d.id} d={d} onOpen={onOpenDecision} />)
              : <div className="decision-card"><p>No decision records yet. Progress can still exist as task updates.</p></div>}
          </div>
        </section>

        <section className="inspector-section">
          <div className="section-heading-row">
            <h3>Evidence receipts</h3>
            <small>{receipts.length} receipts</small>
          </div>
          <div className="receipt-list">
            {receipts.length
              ? receipts.map((r) => <ReceiptCard key={r.message_id} item={r} onOpen={onOpenEvidence} />)
              : <div className="receipt-card"><div className="receipt-copy"><strong>No receipts linked yet</strong><p>Task này chưa có trích dẫn nguồn.</p></div></div>}
          </div>
        </section>
      </div>
    </>
  );
}

export function DecisionInspector({
  decision, bundle, onOpenTask, onOpenDecision, onOpenEvidence, onCloseDecision,
}: Common & { decision: Decision }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const statusText = decision.status.charAt(0).toUpperCase() + decision.status.slice(1);
  const affected = decisionTaskIds(decision);
  const receipts = bundle.evidence.filter((e) =>
    e.backlinks.some((b) => b.type === "decision" && b.id === decision.id));
  const relation = decision.supersedes_decision_id
    ? { label: "Supersedes", id: decision.supersedes_decision_id }
    : decision.superseded_by_decision_id
      ? { label: "Superseded by", id: decision.superseded_by_decision_id }
      : null;

  async function act(kind: "approve" | "reject") {
    const uid = personaUserId(bundle);
    if (uid === undefined) return;
    setBusy(true);
    setNote(null);
    try {
      const outcome = kind === "approve"
        ? await api.approveProposal(personaFromDocument(), uid, decision.id)
        : await api.rejectProposal(personaFromDocument(), uid, decision.id);
      if (!["effective", "rejected"].includes(outcome.status)) setNote(`→ ${outcome.status}`);
      router.refresh();
    } catch (err) {
      setNote((err as Error).message.slice(0, 140));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="inspector-head decision-inspector-head">
        <div className="inspector-head-top">
          <span className="inspector-task-id">{decisionLabel(decision.id)} · Decision</span>
          <div className="inspector-actions">
            <button className="icon-button" aria-label="Đóng chi tiết decision" onClick={onCloseDecision}>
              <Icon name="close" />
            </button>
          </div>
        </div>
        <h2>{decision.description}</h2>
        <div className="inspector-status-row">
          <span className={`decision-status ${decision.status}`}><i></i>{statusText}</span>
          <span className="source-badge">{decisionFacet(decision)}</span>
          <span className="source-badge">{affected.length} affected task{affected.length === 1 ? "" : "s"}</span>
        </div>
        {decision.status === "proposed" && (
          <div className="inspector-write-row">
            <button className="primary-button" disabled={busy} onClick={() => act("approve")}>
              <Icon name="check" /> Duyệt
            </button>
            <button className="secondary-button" disabled={busy} onClick={() => act("reject")}>
              Bỏ qua
            </button>
          </div>
        )}
        {note && <span className="write-note">{note}</span>}
      </div>
      <div className="inspector-body">
        <div className="current-state-card decision-outcome-card">
          <div className="section-kicker">
            Decision outcome
            <span className="verified-label"><Icon name="check" /> authority checked</span>
          </div>
          <p>{decision.context ?? decision.note ?? decision.description}</p>
          <div className="state-facts">
            <div className="state-fact"><span>Status</span><strong>{statusText}</strong></div>
            <div className="state-fact"><span>Scope</span><strong>{decision.scope_target}</strong></div>
            <div className="state-fact"><span>Facet</span><strong>{decisionFacet(decision)}</strong></div>
            <div className="state-fact"><span>Event time</span><strong>{shortDate(decision.ts)}</strong></div>
            <div className="state-fact"><span>Maker</span><strong>@{decision.decided_by_handle ?? decision.decided_by_user_id}</strong></div>
            <div className="state-fact"><span>Receipts</span><strong>{decision.citations.length} pinned</strong></div>
            {decision.approval_via && (
              <div className="state-fact"><span>Approved</span><strong>@{decision.approved_by_handle} · {decision.approval_via}</strong></div>
            )}
            {decision.effect_window && (
              <div className="state-fact">
                <span>Effect window</span>
                <strong>{shortDate(decision.effect_window.from)} → {shortDate(decision.effect_window.until ?? null)}</strong>
              </div>
            )}
          </div>
        </div>

        {relation && (
          <section className="inspector-section">
            <div className="section-heading-row"><h3>Decision relationship</h3><small>Append-only lineage</small></div>
            <button className="decision-relation-card" onClick={() => onOpenDecision(relation.id)}>
              <span><Icon name="decision" /></span>
              <span>
                <small>{relation.label}</small>
                <strong>
                  {decisionLabel(relation.id)} · {bundle.decisions.find((d) => d.id === relation.id)?.description ?? "Related decision"}
                </strong>
              </span>
              <Icon name="chevron" />
            </button>
          </section>
        )}

        <section className="inspector-section">
          <div className="section-heading-row"><h3>Affected tasks</h3><small>{affected.length} linked</small></div>
          <div className="decision-task-list">
            {affected.map((id) => {
              const task = bundle.tasks.find((t) => t.id === id);
              return task ? (
                <button key={id} onClick={() => onOpenTask(id)}>
                  <i className={`related-state ${task.status}`}></i>
                  <span>
                    <strong>{taskLabel(id)} · {task.description}</strong>
                    <small>{statusLabel(task.status)} · {memberName(bundle, task.pics[0])}</small>
                  </span>
                  <Icon name="chevron" />
                </button>
              ) : (
                <button key={id} disabled>
                  <i className="related-state todo"></i>
                  <span>
                    <strong>{taskLabel(id)}</strong>
                    <small>task chưa tồn tại — chờ decision hiệu lực</small>
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="inspector-section">
          <div className="section-heading-row"><h3>Rationale & context</h3><small>Grounded summary</small></div>
          <div className="decision-rationale">
            <p>{decision.note ?? decision.context ?? decision.description}</p>
            <span>Generated only from the decision record and its cited evidence.</span>
          </div>
        </section>

        <section className="inspector-section">
          <div className="section-heading-row"><h3>Evidence receipts</h3><small>{receipts.length} pinned</small></div>
          <div className="receipt-list">
            {receipts.length
              ? receipts.map((r) => <ReceiptCard key={r.message_id} item={r} onOpen={onOpenEvidence} />)
              : <div className="receipt-card"><div className="receipt-copy"><strong>No evidence linked</strong><p>Decision này chưa có trích dẫn.</p></div></div>}
          </div>
        </section>
      </div>
    </>
  );
}
