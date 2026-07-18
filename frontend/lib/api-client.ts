// Shared typed command client (DSH-7). Owner: A ships the real EVM-021 envelope
// client early in P4 (work-split.md interface #6); B's inbox/board taps must use
// THIS module, never hand-roll a write call. Reads are plain fetch wrappers any
// module's FE piece can call directly.
import type { CommandEnvelope } from "./types";

// Server components fetch from INSIDE the frontend container, where the
// browser's localhost:8000 would point at the frontend container itself —
// SSR must use the compose service DNS (API_URL_INTERNAL=http://api:8000);
// the browser keeps NEXT_PUBLIC_API_URL (host-published port).
const API_URL =
  (typeof window === "undefined" ? process.env.API_URL_INTERNAL : undefined) ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

// ngrok's free tier answers browser-shaped requests with an HTML interstitial
// unless this header rides along; harmless against any other backend host.
const BASE_HEADERS = { "ngrok-skip-browser-warning": "1" };

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function responseError(res: Response): Promise<ApiError> {
  const body = await res.json().catch(() => null) as { detail?: unknown } | null;
  const detail = typeof body?.detail === "string" ? body.detail : res.statusText;
  return new ApiError(res.status, detail || `HTTP ${res.status}`);
}

async function apiGet<T>(path: string, persona?: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { ...BASE_HEADERS, ...(persona ? { "X-Persona": persona } : {}) },
    cache: "no-store",
  });
  if (!res.ok) throw await responseError(res);
  return res.json();
}

// The real [EVM-021] envelope: every dashboard tap POSTs one typed command;
// a 409 carries the version-conflict diff card in its body.
async function postCommand<T>(command: CommandEnvelope & Record<string, unknown>): Promise<T> {
  const res = await fetch(`${API_URL}/commands`, {
    method: "POST",
    headers: { ...BASE_HEADERS, "Content-Type": "application/json", "X-Persona": command.persona },
    body: JSON.stringify(command),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`POST /commands failed: ${res.status} ${body}`);
  }
  return res.json();
}

function envelope(persona: string): CommandEnvelope {
  return { client_command_id: crypto.randomUUID(), persona, created_from: "dashboard" };
}

// DSH-7 typed taps — thin wrappers so pages never hand-roll command shapes.
function approveProposal(persona: string, personaUserId: number, decisionId: number) {
  return postCommand<{ status: string }>({
    ...envelope(persona), kind: "approve_proposal",
    decision_id: decisionId, approved_by_user_id: personaUserId,
    ack_revalidation: true,
  });
}

function rejectProposal(
  persona: string, personaUserId: number, decisionId: number,
  reason: "veto" | "dismissed" = "dismissed",
) {
  return postCommand<{ status: string }>({
    ...envelope(persona), kind: "reject_proposal",
    decision_id: decisionId, rejected_by_user_id: personaUserId, reason,
  });
}

function recordTaskStatus(
  persona: string, personaUserId: number, taskId: number, status: string,
) {
  return postCommand<{ status: string }>({
    ...envelope(persona), kind: "record_task_update",
    task_id: taskId, actor_user_id: personaUserId,
    update_kind: "status", payload: { status },
  });
}

async function askQA(question: string, persona: string) {
  const res = await fetch(`${API_URL}/qa`, {
    method: "POST",
    headers: { ...BASE_HEADERS, "Content-Type": "application/json", "X-Persona": persona },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw await responseError(res);
  return res.json();
}

// CAP-3 upload flow (DSH-8) — the one write path that ISN'T a `POST /commands`
// envelope: `/uploads/transcript` takes a raw file, not a typed command
// (architecture.md's API sketch lists it separately for this reason).
async function uploadTranscript(file: File, persona: string): Promise<{ upload_id: number }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/uploads/transcript`, {
    method: "POST",
    headers: { ...BASE_HEADERS, "X-Persona": persona },
    body: form,
  });
  if (!res.ok) throw await responseError(res);
  return res.json();
}

export const api = {
  get: apiGet, postCommand, uploadTranscript,
  approveProposal, rejectProposal, recordTaskStatus, askQA,
};
