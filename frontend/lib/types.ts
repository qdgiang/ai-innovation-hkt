// Mirrors backend/evermind/contracts + the real router response shapes
// (verified live against the running API, not just the Pydantic contracts —
// work-split.md: contracts are "shared, gated"). TS is hand-kept, not
// generated, for the hackathon clock; regenerate from the OpenAPI schema in
// P6 if time allows.

export type DecisionStatus = "proposed" | "effective" | "superseded" | "rejected";
export type TaskStatus = "todo" | "doing" | "done" | "blocked" | "canceled" | "merged";
export type SignalKind = "blocker" | "dependency" | "ask" | "parked";

export interface Persona {
  id: number;
  handle: string | null;
  name: string;
  role_rank: 1 | 2 | 3;
  status: "provisional" | "active" | "departing" | "departed";
}

// The real GET /decisions row (decisions_router._serialize).
export interface Decision {
  id: number;
  ts: string;
  recorded_at: string;
  decided_by_user_id: number;
  decided_by_handle: string | null;
  scope: "task" | "team" | "project";
  scope_target: string;
  description: string;
  context: string | null;
  note: string | null;
  ops: { target: string; facet: string; op: string; value: unknown }[];
  status: DecisionStatus;
  rejected_reason: string | null;
  supersedes_decision_id: number | null;
  superseded_by_decision_id: number | null;
  approved_by_user_id: number | null;
  approved_by_handle: string | null;
  approval_via: string | null;
  created_from: "marker" | "llm" | "dashboard" | "transcript";
  confidence: number | null;
  effect_window: { from: string; until: string | null } | null;
  citations: { message_id: number; kind: "evidence" | "approval" | "corroboration" }[];
}

// POST /qa (KnowledgeService.answer).
export interface QAResponse {
  answer: string;
  sources: string[];
  llm: boolean;
  cited_decision_ids: number[];
  cited_task_ids: number[];
  cited_message_ids: number[];
}

// GET /health/capture (CaptureHealthService.check_all_groups).
export interface CaptureGroupHealth {
  group_id: number;
  last_message_at: string | null;
  dark: boolean;
}

// The real GET /tasks shape (evermind.tasks.models.Task, jsonable_encoder'd).
export interface Task {
  id: number;
  project_id: number;
  project_kind: "campaign" | "program";
  kind: "project" | "ongoing";
  type: "urgent" | "normal" | "undefined";
  description: string;
  status: TaskStatus;
  merged_into: number | null;
  parent_task_id: number | null;
  start_date: string | null;
  end_date: string | null;
  end_date_defaulted: boolean;
  blocked_waiting_on_party_id: number | null;
  blocked_waiting_on_text: string | null;
  blocked_since: string | null;
  note: string | null;
}

export interface ReasoningLogEntry {
  source: "decision" | "update";
  ts: string;
  recorded_at: string;
  // "decision" rows:
  decision_id?: number;
  ops?: { target: string; facet: string; op: string; value: unknown }[];
  retracted?: boolean;
  // "update" rows:
  actor_user_id?: number;
  kind?: string;
  payload?: Record<string, unknown>;
}

export interface TaskReasoning {
  task: Task | null;
  log: ReasoningLogEntry[];
}

export interface DecisionSummary {
  id: number;
  description: string;
  status: DecisionStatus;
  decided_by: string;
  ts: string;
  superseded_by_decision_id?: number | null;
}

// The real GET /feed shape (evermind.surfacing.models.FeedEntry).
export interface FeedEntry {
  id: number;
  persona_user_id: number;
  ts: string;
  kind: string;
  decision_id: number | null;
  task_id: number | null;
  payload: Record<string, unknown>;
  batch_key: string;
  superseded_by_entry: number | null;
}

export interface InboxItem {
  id: number;
  persona_user_id: number;
  kind: "proposal" | "confirm" | "challenge" | "diff" | "triage" | "receipt";
  ref_id: number;
  created_at: string;
  resolved_at?: string | null;
  resolution?: string | null;
}

// GET /blockers?by=party — grouped by counterparty NAME (or free text);
// each group carries asserted-blocked TASKS and PROMOTED weak SIGNALS (SIG-1:
// mentioned ≥2 times or 1 + staleness — mentions are the citations, G27).
export interface BlockedTaskCard {
  task_id: number;
  description: string;
  since: string | null;
}
export interface PromotedSignalCard {
  topic: string;
  kind: "blocker" | "dependency";
  project_id: number;
  task_id: number | null;
  since: string;
  mentions: number;
  citation_message_ids: number[];
  excerpt: string;
}
export type BlockersBoard = Record<
  string,
  { tasks: BlockedTaskCard[]; signals: PromotedSignalCard[] }
>;

// GET /digest/{team} (SurfacingService.digest_for's dict).
export interface Digest {
  team_id: number;
  generated_at: string;
  tasks_by_status: Record<string, number>;
  blockers: {
    task_id: number;
    description: string;
    waiting_on_text: string | null;
    waiting_on_party_id: number | null;
    since: string | null;
  }[];
  needs_attention: { task_id: number; lamp: string }[];
  wrap_note: string | null;
  wrap_note_by: number | null;
}

// [EVM-021] the typed write envelope every dashboard tap sends via `POST /commands`.
export interface CommandEnvelope {
  client_command_id: string;
  persona: string;
  expected_version?: string | null;
  created_from: "dashboard";
}
