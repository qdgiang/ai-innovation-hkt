"use client";

// The knowledge-base workspace app-shell (frontend_ref port): sidebar,
// topbar, project heading, metric strip, view tabs, inspector and overlays —
// all fed by the live GET /workspace bundle passed in from the server page.
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import { personaFromDocument, setPersonaCookie } from "@/lib/persona-client";
import type { CaptureGroupHealth, InboxItem } from "@/lib/types";
import {
  WsBundle, WsProject, avatarClass, decisionLabel, fullDate, initials,
  roleLabel,
} from "@/lib/workspace";
import { Icon } from "./icons";
import { DecisionInspector, TaskInspector } from "./Inspector";
import { AskModal, EvidenceModal, SearchPalette } from "./overlays";
import {
  DecisionsView, EvidenceView, KnowledgeView, MapView, RadarView, ViewProps,
} from "./views";

const NAV = [
  { view: "knowledge", label: "Knowledge base", icon: "grid" },
  { view: "map", label: "Task & decisions", icon: "graph" },
  { view: "decisions", label: "Decision log", icon: "decision" },
  { view: "evidence", label: "Evidence archive", icon: "evidence" },
  { view: "radar", label: "Blocker radar", icon: "radar" },
];

const TABS = [
  { view: "knowledge", label: "Project knowledge" },
  { view: "map", label: "Task & decision panels" },
  { view: "decisions", label: "Decision log" },
  { view: "evidence", label: "Evidence archive" },
];

export function WorkspaceApp({
  bundle, projects, personaHandle, initialView,
}: {
  bundle: WsBundle;
  projects: WsProject[];
  personaHandle: string;
  initialView?: string;
}) {
  const router = useRouter();
  const startView = initialView && NAV.some((n) => n.view === initialView) ? initialView : "knowledge";
  const [view, setViewState] = useState(startView);
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(bundle.tasks[0]?.id ?? null);
  const [selectedDecisionId, setSelectedDecisionId] = useState<number | null>(null);
  const [inspectorMode, setInspectorMode] = useState<"task" | "decision" | null>(
    startView === "map" ? "task" : null,
  );
  const [showInactive, setShowInactive] = useState(true);
  const [evidenceId, setEvidenceId] = useState<number | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [askOpen, setAskOpen] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [inbox, setInbox] = useState<InboxItem[]>([]);
  const [capture, setCapture] = useState<CaptureGroupHealth[] | null>(null);

  const setView = useCallback((next: string) => {
    setViewState(next);
    // map always opens with the task inspector; every other view starts
    // full-width until a decision is explicitly selected
    setInspectorMode(next === "map" ? "task" : null);
  }, []);

  const openTask = useCallback((id: number) => {
    setSelectedTaskId(id);
    setInspectorMode("task");
    setViewState((v) => (v === "map" || v === "tasks" ? v : "map"));
    setSidebarOpen(false);
  }, []);

  const openDecision = useCallback((id: number) => {
    setSelectedDecisionId(id);
    setInspectorMode("decision");
    setViewState((v) => (v === "decisions" ? v : "map"));
  }, []);

  const openEvidence = useCallback((id: number) => setEvidenceId(id), []);

  const closeDecision = useCallback(() => {
    setInspectorMode(view === "decisions" ? null : "task");
  }, [view]);

  // pending inbox (proposals waiting on the current persona) + capture health
  useEffect(() => {
    let alive = true;
    const load = () => {
      api.get<InboxItem[]>("/inbox", personaFromDocument())
        .then((rows) => alive && setInbox(rows.filter((r) => !r.resolved_at)))
        .catch(() => alive && setInbox([]));
      api.get<CaptureGroupHealth[]>("/health/capture")
        .then((rows) => alive && setCapture(rows))
        .catch(() => alive && setCapture(null));
    };
    load();
    const timer = setInterval(load, 30_000);
    return () => { alive = false; clearInterval(timer); };
  }, [bundle]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement).matches?.("input, textarea, [contenteditable='true']");
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
      if (!typing && e.key === "/") {
        e.preventDefault();
        setSearchOpen(true);
      }
      if (e.key === "Escape") {
        setSearchOpen(false);
        setEvidenceId(null);
        setAskOpen(false);
        setBellOpen(false);
        setSidebarOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const persona = bundle.members.find((m) => m.handle === personaHandle);
  const selectedTask = bundle.tasks.find((t) => t.id === selectedTaskId) ?? bundle.tasks[0] ?? null;
  const selectedDecision = bundle.decisions.find((d) => d.id === selectedDecisionId) ?? null;
  const selectedEvidence = bundle.evidence.find((e) => e.message_id === evidenceId) ?? null;
  const blockerCount = bundle.counts.blockers;
  const darkGroups = capture?.filter((g) => g.dark).length ?? 0;

  const showInspector = (view === "map" && inspectorMode !== null)
    || (view === "decisions" && inspectorMode === "decision" && selectedDecision !== null);
  const gridClass = view === "knowledge"
    ? "workspace-grid knowledge-mode"
    : showInspector ? "workspace-grid" : "workspace-grid full-width-mode";

  const viewProps: ViewProps = {
    bundle, selectedTaskId, onOpenTask: openTask, onOpenDecision: openDecision,
    onOpenEvidence: openEvidence, onSetView: setView,
  };
  const inspectorProps = {
    bundle, showInactive, onToggleInactive: setShowInactive,
    onOpenTask: openTask, onOpenDecision: openDecision,
    onOpenEvidence: openEvidence, onCloseDecision: closeDecision,
  };

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark" aria-hidden="true"><span></span><span></span><span></span></div>
          <div>
            <div className="brand-name">EverMind</div>
            <div className="brand-caption">Organizational memory</div>
          </div>
          <button className="sidebar-close icon-button" aria-label="Đóng menu" onClick={() => setSidebarOpen(false)}>
            <Icon name="close" />
          </button>
        </div>

        <nav className="primary-nav" aria-label="Điều hướng chính">
          <p className="nav-label">Workspace</p>
          {NAV.map((item) => (
            <button
              key={item.view}
              className={`nav-item ${view === item.view ? "active" : ""}`}
              onClick={() => { setView(item.view); setSidebarOpen(false); }}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {item.view === "map" && <span className="nav-count">{bundle.counts.tasks}</span>}
              {item.view === "decisions" && <span className="nav-count">{bundle.counts.decisions}</span>}
              {item.view === "evidence" && <span className="nav-count">{bundle.counts.receipts}</span>}
              {item.view === "radar" && blockerCount > 0 && <span className="nav-dot"></span>}
            </button>
          ))}

          <p className="nav-label projects-label">Projects</p>
          {projects.map((p, i) => (
            <button
              key={p.id}
              className={`project-nav ${p.id === bundle.project.id ? "active" : ""}`}
              onClick={() => router.push(`/?project=${p.id}`)}
            >
              <span className={`project-color ${i % 2 === 0 ? "coral" : "blue"}`}></span>
              <span className="project-nav-copy">
                <strong>{p.name}</strong>
                <small>{p.kind === "campaign" ? "Campaign" : "Program"} · {p.task_count ?? 0} tasks</small>
              </span>
              <Icon name="chevron" />
            </button>
          ))}
        </nav>

        <div className="capture-card">
          <div className="capture-pulse"><span></span></div>
          <div>
            <strong>
              {capture === null ? "Capture status unknown"
                : darkGroups > 0 ? `Memory capture — ${darkGroups} group dark` : "Memory capture active"}
            </strong>
            <small>{capture ? `${capture.length} groups theo dõi` : "đang kiểm tra…"}</small>
          </div>
        </div>

        <div className="profile-row">
          <div className={`avatar ${avatarClass(persona?.id)}`}>{initials(persona?.name ?? personaHandle)}</div>
          <div className="profile-copy">
            <select
              aria-label="Đổi persona (demo, không xác thực)"
              value={personaHandle}
              onChange={(e) => {
                setPersonaCookie(e.target.value);
                router.refresh();
              }}
            >
              {bundle.members.filter((m) => m.handle).map((m) => (
                <option key={m.id} value={m.handle!}>{m.name}</option>
              ))}
            </select>
            <small>{persona ? roleLabel(persona, bundle.teams) : "demo persona"}</small>
          </div>
        </div>
      </aside>

      {sidebarOpen && <div className="sidebar-scrim open" onClick={() => setSidebarOpen(false)}></div>}

      <main className="main-area">
        <header className="topbar">
          <button className="mobile-menu icon-button" aria-label="Mở menu" onClick={() => setSidebarOpen(true)}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
          </button>
          <button className="search-trigger" aria-label="Tìm trong knowledge base" onClick={() => setSearchOpen(true)}>
            <Icon name="search" />
            <span>Tìm task, decision hoặc evidence…</span>
            <kbd>⌘ K</kbd>
          </button>
          <div className="topbar-actions">
            <div className="bell-wrap">
              <button className="icon-button notification-button" aria-label="Thông báo" onClick={() => setBellOpen((v) => !v)}>
                <Icon name="bell" />
                {inbox.length > 0 && <span></span>}
              </button>
              {bellOpen && (
                <div className="bell-menu">
                  <h4>Chờ bạn xử lý</h4>
                  {inbox.length === 0 && <div className="bell-empty">Không có mục nào đang chờ.</div>}
                  {inbox.slice(0, 6).map((item) => (
                    <button
                      key={item.id}
                      onClick={() => {
                        setBellOpen(false);
                        if (item.kind === "proposal" || item.kind === "challenge") openDecision(item.ref_id);
                        else openTask(item.ref_id);
                      }}
                    >
                      <Icon name={item.kind === "confirm" ? "task" : "decision"} />
                      <span>
                        <strong>
                          {item.kind === "proposal" ? `Duyệt ${decisionLabel(item.ref_id)}`
                            : item.kind === "confirm" ? `Xác nhận cập nhật task #${item.ref_id}`
                              : `${item.kind} #${item.ref_id}`}
                        </strong>
                        <small>{new Date(item.created_at).toLocaleString("vi-VN")}</small>
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className={`avatar ${avatarClass(persona?.id)} top-avatar`}>{initials(persona?.name ?? personaHandle)}</div>
          </div>
        </header>

        <section className="page-content">
          <div className="breadcrumb">
            <span>Projects</span>
            <Icon name="chevron" />
            <strong>{bundle.project.name}</strong>
          </div>

          <div className="project-heading">
            <div className="project-heading-main">
              <div className="project-symbol">月</div>
              <div>
                <div className="heading-eyebrow">
                  <span className="status-pill campaign">{bundle.project.kind === "campaign" ? "Campaign" : "Program"}</span>
                  <span className="heading-date">{fullDate(bundle.project.end_date)}</span>
                </div>
                <h1>{bundle.project.name}</h1>
                <p>{bundle.teams.map((t) => t.name).join(" · ") || "—"}</p>
              </div>
            </div>
            <div className="heading-actions">
              <button className="primary-button" onClick={() => setAskOpen(true)}>
                <Icon name="message" />
                Ask EverMind
              </button>
            </div>
          </div>

          <div className="metric-strip" aria-label="Project summary">
            <div className="metric-card">
              <span className="metric-icon tasks"><Icon name="task" /></span>
              <div><strong>{bundle.counts.tasks}</strong><span>Tasks</span></div>
              <small>{bundle.counts.active_tasks} active</small>
            </div>
            <div className="metric-card">
              <span className="metric-icon decisions"><Icon name="decision" /></span>
              <div><strong>{bundle.counts.decisions}</strong><span>Decisions</span></div>
              <small>{bundle.counts.superseded} superseded</small>
            </div>
            <div className={`metric-card ${blockerCount > 0 ? "warning" : ""}`}>
              <span className="metric-icon blockers"><svg viewBox="0 0 24 24"><path d="M12 3 2.8 19h18.4L12 3ZM12 9v4M12 17h.01" /></svg></span>
              <div><strong>{blockerCount}</strong><span>Blockers</span></div>
              <small>{blockerCount > 0 ? "needs action" : "clear"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-icon evidence"><Icon name="evidence" /></span>
              <div><strong>{bundle.counts.receipts}</strong><span>Receipts</span></div>
              <small>{bundle.counts.proposed} chờ duyệt</small>
            </div>
          </div>

          <div className="view-toolbar">
            <div className="view-tabs" role="tablist" aria-label="Project views">
              {TABS.map((tab) => (
                <button
                  key={tab.view}
                  className={`view-tab ${view === tab.view ? "active" : ""}`}
                  role="tab"
                  aria-selected={view === tab.view}
                  onClick={() => setView(tab.view)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="toolbar-actions">
              <button className="compact-button">
                <span className="team-swatch"></span> {bundle.teams[0]?.name ?? "team"}
              </button>
            </div>
          </div>

          <div className={gridClass}>
            <section className="view-panel" aria-live="polite">
              {view === "knowledge" && <KnowledgeView {...viewProps} />}
              {view === "map" && <MapView {...viewProps} />}
              {view === "decisions" && <DecisionsView {...viewProps} onSelectDecision={openDecision} />}
              {view === "evidence" && <EvidenceView {...viewProps} />}
              {view === "radar" && <RadarView {...viewProps} />}
            </section>
            {showInspector && (
              <aside className="inspector" aria-label="Chi tiết">
                {inspectorMode === "decision" && selectedDecision
                  ? <DecisionInspector decision={selectedDecision} {...inspectorProps} />
                  : selectedTask
                    ? <TaskInspector task={selectedTask} {...inspectorProps} />
                    : null}
              </aside>
            )}
          </div>
        </section>
      </main>

      {searchOpen && (
        <SearchPalette
          bundle={bundle}
          onClose={() => setSearchOpen(false)}
          onOpenTask={openTask}
          onOpenDecision={openDecision}
          onOpenEvidence={openEvidence}
        />
      )}
      {selectedEvidence && (
        <EvidenceModal
          item={selectedEvidence}
          bundle={bundle}
          onClose={() => setEvidenceId(null)}
          onOpenTask={openTask}
          onOpenDecision={openDecision}
        />
      )}
      {askOpen && (
        <AskModal
          onClose={() => setAskOpen(false)}
          onOpenTask={openTask}
          onOpenDecision={openDecision}
          onOpenEvidence={openEvidence}
        />
      )}
    </div>
  );
}
