// Mirrors backend/evermind/contracts — keep in lockstep with any contract-change PR
// (work-split.md: contracts are "shared, gated"). TS is hand-kept, not generated,
// for the hackathon clock; regenerate from the OpenAPI schema in P6 if time allows.

export type DecisionStatus = "proposed" | "effective" | "superseded" | "rejected";
export type TaskStatus = "todo" | "doing" | "done" | "blocked" | "canceled" | "merged";
export type SignalKind = "blocker" | "dependency" | "ask" | "parked";

export interface Persona {
  id: number;
  name: string;
  role_rank: 1 | 2 | 3;
}

export interface TaskSummary {
  id: number;
  description: string;
  status: TaskStatus;
  pics: string[];
  team?: string;
  end_date?: string | null;
}

export interface DecisionSummary {
  id: number;
  description: string;
  status: DecisionStatus;
  decided_by: string;
  ts: string;
  superseded_by_decision_id?: number | null;
}

export interface FeedEntry {
  id: number;
  ts: string;
  kind: string;
  payload: Record<string, unknown>;
}

export interface InboxItem {
  id: number;
  kind: "proposal" | "confirm" | "challenge" | "diff" | "triage" | "receipt";
  ref_id: number;
  created_at: string;
  resolved_at?: string | null;
}

// [EVM-021] the typed write envelope every dashboard tap sends via `POST /commands`.
export interface CommandEnvelope {
  client_command_id: string;
  persona: string;
  expected_version?: string | null;
  created_from: "dashboard";
}
