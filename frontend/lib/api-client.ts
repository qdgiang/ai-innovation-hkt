// Shared typed command client (DSH-7). Owner: A ships the real EVM-021 envelope
// client early in P4 (work-split.md interface #6); B's inbox/board taps must use
// THIS module, never hand-roll a write call. Reads are plain fetch wrappers any
// module's FE piece can call directly.
import type { CommandEnvelope } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiGet<T>(path: string, persona?: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: persona ? { "X-Persona": persona } : undefined,
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

// TODO(A): replace with the real typed envelope + expected_version/diff-card
// handling once DEC-* lands (P4/P5). This is a placeholder shape only.
async function postCommand<T>(command: CommandEnvelope & Record<string, unknown>): Promise<T> {
  const res = await fetch(`${API_URL}/commands`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Persona": command.persona },
    body: JSON.stringify(command),
  });
  if (!res.ok) throw new Error(`POST /commands failed: ${res.status}`);
  return res.json();
}

export const api = { get: apiGet, postCommand };
