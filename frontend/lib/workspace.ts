// Types + view helpers for the knowledge-base workspace (GET /workspace/{id}),
// mirroring frontend_ref's data shapes but fed by the live projections.
import type { Decision } from "./types";

export interface WsProject {
  id: number;
  name: string;
  kind: "campaign" | "program";
  status: string;
  end_date: string | null;
  task_count?: number;
}

export interface WsMember {
  id: number;
  handle: string | null;
  name: string;
  role_rank: 1 | 2 | 3;
  status: string;
  team_ids: number[];
  leads_team_ids: number[];
  pic_task_ids: number[];
}

export interface WsDep {
  task_id: number;
  status: string;
}

export interface WsTask {
  id: number;
  project_id: number;
  kind: string;
  type: string;
  description: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
  end_date_defaulted: boolean;
  blocked_waiting_on_party_id: number | null;
  blocked_waiting_on_text: string | null;
  blocked_since: string | null;
  note: string | null;
  pics: number[];
  team_ids: number[];
  blocks: WsDep[];
  waits_on: WsDep[];
  decision_ids: number[];
  facts: Record<string, unknown>;
  update_count: number;
  last_update_ts: string | null;
}

export interface WsBacklink {
  type: "decision" | "task";
  id: number;
  label: string;
  role: string;
}

export interface WsEvidence {
  message_id: number;
  source: string;
  channel: string | null;
  author_identity: string;
  author_user_id: number | null;
  ts: string;
  text: string;
  rev: number;
  thread_ref: number | null;
  raw_ref: string;
  backlinks: WsBacklink[];
}

export interface WsBundle {
  project: WsProject;
  teams: { id: number; name: string }[];
  members: WsMember[];
  tasks: WsTask[];
  decisions: Decision[];
  evidence: WsEvidence[];
  counts: {
    tasks: number;
    active_tasks: number;
    decisions: number;
    superseded: number;
    proposed: number;
    blockers: number;
    receipts: number;
  };
}

export const taskLabel = (id: number) => `T-${String(id).padStart(2, "0")}`;
export const decisionLabel = (id: number) => `D-${String(id).padStart(2, "0")}`;
export const messageLabel = (id: number) => `m${String(id).padStart(4, "0")}`;

export const STATUS_LABEL: Record<string, string> = {
  todo: "To do",
  doing: "In progress",
  blocked: "Blocked",
  done: "Done",
  canceled: "Canceled",
  merged: "Merged",
};
export const statusLabel = (s: string) => STATUS_LABEL[s] ?? s;

export const CITATION_ROLE: Record<string, string> = {
  evidence: "evidence",
  approval: "approves",
  corroboration: "supports",
  reports: "reports",
};

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  const last = parts[parts.length - 1] ?? "";
  const first = parts.length > 1 ? parts[0] : "";
  return ((first[0] ?? "") + (last[0] ?? "")).toUpperCase() || "?";
}

export function avatarClass(userId: number | null | undefined): string {
  return `avatar-p${Math.abs(userId ?? 0) % 8}`;
}

export function roleLabel(m: WsMember, teams: { id: number; name: string }[]): string {
  if (m.role_rank === 3) return "Coordinator";
  if (m.role_rank === 2) {
    const led = teams.find((t) => m.leads_team_ids.includes(t.id));
    return led ? `${led.name} team lead` : "Team lead";
  }
  return m.status === "provisional" ? "Provisional member" : "Member";
}

// Display timezone is the ORG's (backend ORG_TIMEZONE contract), never the
// machine's: the workspace bundle is SSR-ed with data, so an unpinned zone
// renders one date on the server (UTC container) and another in the browser
// (+07:00) — a guaranteed React hydration mismatch on top of being wrong.
export const ORG_TZ = "Asia/Ho_Chi_Minh";

export function shortDate(ts: string | null | undefined): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleDateString("vi-VN", {
    day: "2-digit", month: "2-digit", timeZone: ORG_TZ,
  });
}

export function fullDate(ts: string | null | undefined): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleDateString("vi-VN", {
    day: "2-digit", month: "2-digit", year: "numeric", timeZone: ORG_TZ,
  });
}

/** Task ids a decision touches: scope target + every op target. */
export function decisionTaskIds(d: Decision): number[] {
  const ids = new Set<number>();
  const collect = (target: string) => {
    const [kind, raw] = target.split(":");
    if (kind === "task" && /^\d+$/.test(raw ?? "")) ids.add(Number(raw));
  };
  collect(d.scope_target);
  for (const op of d.ops) collect(op.target);
  return [...ids];
}

/** Primary facet a decision writes (shown as the "facet" chip). */
export function decisionFacet(d: Decision): string {
  return d.ops[0]?.facet ?? d.scope;
}
