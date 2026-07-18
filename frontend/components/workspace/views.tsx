"use client";

// The five workspace views, ported from frontend_ref and fed live data.
import { useState } from "react";
import {
  WsBundle, WsTask, avatarClass, decisionFacet, decisionLabel, decisionTaskIds,
  fullDate, initials, messageLabel, roleLabel, shortDate, statusLabel, taskLabel,
} from "@/lib/workspace";
import { Icon } from "./icons";

export interface ViewProps {
  bundle: WsBundle;
  selectedTaskId: number | null;
  onOpenTask: (id: number) => void;
  onOpenDecision: (id: number) => void;
  onOpenEvidence: (id: number) => void;
  onSetView: (view: string) => void;
}

function personName(bundle: WsBundle, userId: number | null | undefined): string {
  return bundle.members.find((m) => m.id === userId)?.name ?? "—";
}

function MiniAvatar({ bundle, userId }: { bundle: WsBundle; userId: number | null | undefined }) {
  const name = personName(bundle, userId);
  return (
    <span className={`mini-avatar ${avatarClass(userId)}`} title={name}>
      {initials(name)}
    </span>
  );
}

// ── Knowledge (project overview composed from live projections) ────────────

export function KnowledgeView(props: ViewProps) {
  const { bundle, onOpenTask, onOpenDecision, onOpenEvidence, onSetView } = props;
  const { project, counts } = bundle;
  const coordinator = bundle.members.find((m) => m.role_rank === 3);
  const leadTeam = bundle.teams[0];

  const picture = [...bundle.tasks]
    .sort((a, b) => {
      const rank = (t: WsTask) => (t.status === "blocked" ? 0 : t.status === "doing" ? 1 : t.status === "todo" ? 2 : 3);
      return rank(a) - rank(b);
    })
    .slice(0, 3);

  const effective = bundle.decisions.filter((d) => d.status === "effective");
  const milestones = [...effective].reverse().slice(-4);
  const pending = bundle.decisions.filter((d) => d.status === "proposed");
  const heroDecision = effective[0];
  const heroTask = picture[0];

  return (
    <div className="kb-shell">
      <nav className="kb-doc-nav" aria-label="Project knowledge documents">
        <div className="kb-nav-head">
          <div>
            <span>Knowledge base</span>
            <strong>{project.name}</strong>
          </div>
        </div>
        <div className="kb-nav-scroll">
          <section className="kb-nav-group">
            <h3>Project</h3>
            <button className="kb-doc-link active">
              <span className="kb-doc-icon"><Icon name="link" /></span>
              <span><strong>Overview</strong><small>live projection</small></span>
            </button>
          </section>
          <section className="kb-nav-group kb-collections">
            <h3>Linked collections</h3>
            <button className="kb-collection-link" onClick={() => onSetView("map")}>
              <Icon name="task" /><span>Tasks</span><strong>{counts.tasks}</strong>
            </button>
            <button className="kb-collection-link" onClick={() => onSetView("decisions")}>
              <Icon name="decision" /><span>Decisions</span><strong>{counts.decisions}</strong>
            </button>
            <button className="kb-collection-link" onClick={() => onSetView("evidence")}>
              <Icon name="evidence" /><span>Evidence</span><strong>{counts.receipts}</strong>
            </button>
          </section>
        </div>
      </nav>

      <article className="kb-article">
        <header className="kb-article-head">
          <div className="kb-article-kicker">
            <span>Project</span><span>·</span><span>Live projection</span>
          </div>
          <h2>Project overview</h2>
          <p>Mục tiêu, bức tranh vận hành và con người phía sau dự án — dựng trực tiếp từ decisions, tasks và evidence đã capture.</p>
          {coordinator && (
            <div className="kb-byline">
              <span className={`avatar ${avatarClass(coordinator.id)}`}>{initials(coordinator.name)}</span>
              <span><strong>{coordinator.name}</strong><small>Coordinator</small></span>
              <div className="kb-tags"><span>{project.kind}</span><span>{project.status}</span></div>
            </div>
          )}
        </header>

        <div className="kb-article-body">
          <section className="kb-hero-note">
            <div className="kb-hero-icon">月</div>
            <div>
              <span className="section-kicker">Project summary</span>
              <p>
                {project.name} — {project.kind === "campaign" ? "chiến dịch có ngày kết thúc" : "chương trình dài hạn"}.
                Mọi thay đổi trọng yếu được ghi thành decision có trích dẫn; tiến độ hằng ngày nằm ở task updates.
              </p>
            </div>
          </section>

          <section className="kb-property-grid" aria-label="Project properties">
            <div><span>Status</span><strong><i className="property-dot active"></i>{project.status}</strong></div>
            <div><span>{project.kind === "campaign" ? "Event date" : "End date"}</span><strong>{fullDate(project.end_date)}</strong></div>
            <div><span>Lead team</span><strong>{leadTeam?.name ?? "—"}</strong></div>
            <div><span>Coordinator</span><strong>{coordinator?.name ?? "—"}</strong></div>
            <div><span>Tasks</span><strong>{counts.active_tasks} active / {counts.tasks}</strong></div>
            <div><span>Knowledge health</span><strong><i className="property-dot healthy"></i>{counts.receipts} receipts linked</strong></div>
          </section>

          <section className="kb-content-section">
            <div className="kb-section-title">
              <div><span>01</span><h3>Mô hình vận hành</h3></div>
              <button onClick={() => onSetView("decisions")}>Open decision log →</button>
            </div>
            <p>
              Dự án chạy theo mô hình decision-driven: thay đổi về đơn hàng, phân công, lịch và chính sách
              được capture thành decision (kèm nguồn chat/transcript nguyên văn), có thẩm quyền và có thể bị
              thay thế (supersede) — lịch sử không bao giờ bị ghi đè.
            </p>
            <div className="kb-inline-links">
              {heroTask && (
                <button onClick={() => onOpenTask(heroTask.id)}>
                  <Icon name="task" />{taskLabel(heroTask.id)} · {heroTask.description.slice(0, 28)}
                </button>
              )}
              {heroDecision && (
                <button onClick={() => onOpenDecision(heroDecision.id)}>
                  <Icon name="decision" />{decisionLabel(heroDecision.id)} · {heroDecision.description.slice(0, 28)}
                </button>
              )}
              {heroDecision?.citations[0] && (
                <button onClick={() => onOpenEvidence(heroDecision.citations[0].message_id)}>
                  <Icon name="evidence" />Receipt {messageLabel(heroDecision.citations[0].message_id)}
                </button>
              )}
            </div>
          </section>

          <section className="kb-content-section">
            <div className="kb-section-title">
              <div><span>02</span><h3>Current operating picture</h3></div>
              <button onClick={() => onSetView("map")}>Open task panels →</button>
            </div>
            <div className="kb-situation-grid">
              {picture.map((t) => (
                <button
                  key={t.id}
                  className={`kb-situation-card ${t.status === "blocked" ? "blocked" : ""}`}
                  onClick={() => onOpenTask(t.id)}
                >
                  <span className={`situation-status ${t.status === "blocked" ? "blocked" : t.status}`}>
                    <i></i>{t.status === "blocked" ? "Needs action" : statusLabel(t.status)}
                  </span>
                  <strong>{t.description}</strong>
                  <p>
                    {t.status === "blocked"
                      ? `Đang chờ ${t.blocked_waiting_on_text ?? "bên ngoài"}.`
                      : t.note ?? `${t.decision_ids.length} decisions · ${t.update_count} updates.`}
                  </p>
                  <small>{taskLabel(t.id)} · {personName(bundle, t.pics[0])} · due {shortDate(t.end_date)}</small>
                </button>
              ))}
            </div>
          </section>

          <section className="kb-content-section kb-milestones">
            <div className="kb-section-title">
              <div><span>03</span><h3>Decision milestones</h3></div>
              <small>Event time</small>
            </div>
            {milestones.map((d, i) => (
              <div
                key={d.id}
                className={`milestone-row ${i < milestones.length - 1 ? "done" : "current"}`}
                role="button"
                tabIndex={0}
                onClick={() => onOpenDecision(d.id)}
              >
                <time>{shortDate(d.ts)}</time><i></i>
                <div>
                  <strong>{d.description}</strong>
                  <small>{decisionLabel(d.id)} · @{d.decided_by_handle ?? d.decided_by_user_id}</small>
                </div>
              </div>
            ))}
            {project.end_date && (
              <div className="milestone-row">
                <time>{shortDate(project.end_date)}</time><i></i>
                <div><strong>{project.kind === "campaign" ? "Event day" : "Milestone"}</strong><small>{project.name}</small></div>
              </div>
            )}
          </section>
        </div>
      </article>

      <aside className="kb-context" aria-label="Project context">
        <section className="kb-context-section">
          <div className="kb-context-heading"><h3>Project members</h3><span>{bundle.members.length}</span></div>
          <div className="kb-member-list">
            {bundle.members.map((m) => (
              <button className="kb-member-row" key={m.id}>
                <span className={`avatar ${avatarClass(m.id)}`}>{initials(m.name)}</span>
                <span>
                  <strong>{m.name}</strong>
                  <small>{roleLabel(m, bundle.teams)}</small>
                  <em>{m.pic_task_ids.length ? `PIC: ${m.pic_task_ids.map(taskLabel).join(", ")}` : "chưa nhận task"}</em>
                </span>
              </button>
            ))}
          </div>
        </section>

        {pending.length > 0 && (
          <section className="kb-context-section">
            <div className="kb-context-heading"><h3>Đang chờ duyệt</h3><span>{pending.length}</span></div>
            <div className="kb-pending-list">
              {pending.map((d) => (
                <button key={d.id} onClick={() => onOpenDecision(d.id)}>
                  <Icon name="decision" />
                  <span>
                    <strong>{decisionLabel(d.id)} · {d.description}</strong>
                    <small>@{d.decided_by_handle ?? d.decided_by_user_id} đề xuất · {shortDate(d.ts)}</small>
                  </span>
                </button>
              ))}
            </div>
          </section>
        )}

        <section className="kb-context-section">
          <div className="kb-context-heading"><h3>Related decisions</h3><button onClick={() => onSetView("decisions")}>View log</button></div>
          <div className="kb-related-list decision-links">
            {effective.slice(0, 4).map((d) => (
              <button key={d.id} onClick={() => onOpenDecision(d.id)}>
                <Icon name="decision" />
                <span>
                  <strong>{decisionLabel(d.id)} · {d.description}</strong>
                  <small>{d.status} · {shortDate(d.ts)}</small>
                </span>
              </button>
            ))}
          </div>
        </section>
      </aside>
    </div>
  );
}

// ── Task & decision panels (graph + inspector) ─────────────────────────────

export function MapView(props: ViewProps) {
  const { bundle, selectedTaskId, onOpenTask } = props;
  return (
    <>
      <div className="panel-header">
        <div className="panel-title-group">
          <h2>Project knowledge graph</h2>
          <p>Chọn một task để mở decisions và receipts liên quan</p>
        </div>
        <div className="legend" aria-label="Chú thích">
          <span><i></i> Active</span>
          <span className="legend-blocked"><i></i> Blocked</span>
          <span className="legend-dependency"><i></i> Dependency</span>
        </div>
      </div>
      <div className="knowledge-canvas">
        <div className="project-root">
          <div className="root-icon">月</div>
          <div className="root-copy">
            <span className="node-kicker">Project</span>
            <strong>{bundle.project.name}</strong>
            <small>{bundle.project.kind} · {bundle.teams[0]?.name ?? ""} · {shortDate(bundle.project.end_date)}</small>
          </div>
          <div className="root-stats"><strong>{bundle.counts.tasks}</strong><small>tasks</small></div>
        </div>
        <div className="root-connector"></div>
        <div className="task-network">
          {bundle.tasks.map((t) => {
            const dep = t.waits_on[0];
            return (
              <article
                key={t.id}
                className={`task-node ${t.status} ${t.id === selectedTaskId ? "selected" : ""}`}
                tabIndex={0}
                role="button"
                aria-label={`Mở ${taskLabel(t.id)} ${t.description}`}
                onClick={() => onOpenTask(t.id)}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onOpenTask(t.id)}
              >
                <div className="task-node-top">
                  <span className="task-id">{taskLabel(t.id)}</span>
                  <span className={`task-state ${t.status}`}><i></i>{statusLabel(t.status)}</span>
                </div>
                <h3>{t.description}</h3>
                <div className="task-meta-row">
                  <div className="mini-avatars">
                    {t.pics.length
                      ? t.pics.map((uid) => <MiniAvatar key={uid} bundle={bundle} userId={uid} />)
                      : <span className="no-dependency">PIC-null</span>}
                  </div>
                  <span>Due {shortDate(t.end_date)}</span>
                </div>
                <div className="task-node-footer">
                  <span className="decision-count">
                    <Icon name="decision" />{t.decision_ids.length} decision{t.decision_ids.length === 1 ? "" : "s"}
                  </span>
                  {dep
                    ? <span className="dependency-chip" title={`Chờ ${taskLabel(dep.task_id)}`}><Icon name="dependency" />{taskLabel(dep.task_id)}</span>
                    : <span className="no-dependency">No dependency</span>}
                </div>
              </article>
            );
          })}
        </div>
        <div className="canvas-footer">
          <span><Icon name="dependency" /> Dependency là graph edge, không phải cây thư mục</span>
        </div>
      </div>
    </>
  );
}

// ── Decision log (full-width list) ─────────────────────────────────────────

export function DecisionsView(props: ViewProps & { onSelectDecision: (id: number) => void }) {
  const { bundle, onSelectDecision } = props;
  const [filter, setFilter] = useState<"all" | "effective" | "proposed" | "inactive">("all");
  const rows = bundle.decisions.filter((d) => {
    if (filter === "all") return true;
    if (filter === "inactive") return d.status === "superseded" || d.status === "rejected";
    return d.status === filter;
  });
  return (
    <div className="list-view">
      <div className="list-view-header">
        <div>
          <h2>Decision log</h2>
          <p>Append-only history with authority, supersession and receipts</p>
        </div>
        <div className="filter-chips">
          {(["all", "effective", "proposed", "inactive"] as const).map((f) => (
            <button
              key={f}
              className={`filter-chip ${filter === f ? "active" : ""}`}
              onClick={() => setFilter(f)}
            >
              {f === "all" ? `All ${bundle.decisions.length}` : f}
            </button>
          ))}
        </div>
      </div>
      <div className="list-cards">
        {rows.map((d) => (
          <article className="wide-card" key={d.id} role="button" tabIndex={0}
            onClick={() => onSelectDecision(d.id)}
            onKeyDown={(e) => e.key === "Enter" && onSelectDecision(d.id)}>
            <span className="decision-card-id">{decisionLabel(d.id)}</span>
            <span className="wide-card-title">
              <strong>{d.description}</strong>
              <small>{decisionTaskIds(d).map(taskLabel).join(" · ") || d.scope_target} · {decisionFacet(d)}</small>
            </span>
            <span className="wide-card-context">
              {d.context ?? d.note ?? `@${d.decided_by_handle ?? d.decided_by_user_id} · ${shortDate(d.ts)}`}
            </span>
            <span className={`decision-status ${d.status}`}><i></i>{d.status}</span>
            <span className="wide-card-arrow"><Icon name="chevron" /></span>
          </article>
        ))}
        {rows.length === 0 && <div className="radar-empty">Không có decision nào khớp bộ lọc.</div>}
      </div>
    </div>
  );
}

// ── Evidence archive ───────────────────────────────────────────────────────

export function EvidenceView(props: ViewProps) {
  const { bundle, onOpenEvidence } = props;
  const [filter, setFilter] = useState<"all" | "chat" | "transcript">("all");
  const rows = bundle.evidence.filter((e) =>
    filter === "all" ? true : filter === "transcript" ? e.source === "transcript" : e.source !== "transcript");
  return (
    <div className="list-view">
      <div className="list-view-header">
        <div>
          <h2>Evidence archive</h2>
          <p>Immutable source revisions with typed backlinks</p>
        </div>
        <div className="filter-chips">
          <button className={`filter-chip ${filter === "all" ? "active" : ""}`} onClick={() => setFilter("all")}>All sources</button>
          <button className={`filter-chip ${filter === "chat" ? "active" : ""}`} onClick={() => setFilter("chat")}>Chat</button>
          <button className={`filter-chip ${filter === "transcript" ? "active" : ""}`} onClick={() => setFilter("transcript")}>Transcripts</button>
        </div>
      </div>
      <div className="evidence-grid">
        {rows.map((item) => (
          <article className="evidence-tile" key={item.message_id} role="button" tabIndex={0}
            onClick={() => onOpenEvidence(item.message_id)}
            onKeyDown={(e) => e.key === "Enter" && onOpenEvidence(item.message_id)}>
            <div className="evidence-tile-top">
              <span className="evidence-tile-source">
                <Icon name={item.source === "transcript" ? "evidence" : "telegram"} />
                {messageLabel(item.message_id)} · {item.source === "transcript" ? "Transcript" : "Chat"}
              </span>
              <span className="revision-badge">rev {item.rev}</span>
            </div>
            <blockquote>“{item.text.length > 150 ? `${item.text.slice(0, 147)}…` : item.text}”</blockquote>
            <div className="evidence-tile-bottom">
              <span>@{item.author_identity} · {shortDate(item.ts)}</span>
              <span className="evidence-links">
                {item.backlinks.slice(0, 2).map((b, i) => (
                  <span className="evidence-link-chip" key={i}>
                    {b.type === "decision" ? decisionLabel(b.id) : taskLabel(b.id)}
                  </span>
                ))}
              </span>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

// ── Blocker radar ──────────────────────────────────────────────────────────

export function RadarView(props: ViewProps) {
  const { bundle, onOpenTask } = props;
  const blocked = bundle.tasks.filter((t) => t.status === "blocked");
  const byParty = blocked.reduce<Record<string, WsTask[]>>((acc, t) => {
    const key = t.blocked_waiting_on_text ?? (t.blocked_waiting_on_party_id != null ? `party #${t.blocked_waiting_on_party_id}` : "không rõ");
    (acc[key] ||= []).push(t);
    return acc;
  }, {});
  return (
    <div className="list-view">
      <div className="list-view-header">
        <div>
          <h2>Blocker radar</h2>
          <p>Task đang chờ bên ngoài, gom theo đối tác — từ marker !blocked và updates</p>
        </div>
      </div>
      {blocked.length === 0 ? (
        <div className="radar-empty">
          Không có blocker nào đang mở. 🎉
        </div>
      ) : (
        <div className="radar-groups">
          {Object.entries(byParty).map(([party, tasks]) => (
            <div className="radar-party" key={party}>
              <h3><i></i>{party}</h3>
              {tasks.map((t) => (
                <button key={t.id} onClick={() => onOpenTask(t.id)}>
                  <span>
                    <strong>{taskLabel(t.id)} · {t.description}</strong>
                    <small>blocked từ {shortDate(t.blocked_since)} · PIC {personName(bundle, t.pics[0])}</small>
                  </span>
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
