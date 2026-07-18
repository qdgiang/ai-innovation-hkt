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

// CAP-3 upload flow (DSH-8) — the one write path that ISN'T a `POST /commands`
// envelope: `/uploads/transcript` takes a raw file, not a typed command
// (architecture.md's API sketch lists it separately for this reason).
async function uploadTranscript(file: File, persona: string): Promise<{ upload_id: number }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/uploads/transcript`, {
    method: "POST",
    headers: { "X-Persona": persona },
    body: form,
  });
  if (!res.ok) throw new Error(`POST /uploads/transcript failed: ${res.status}`);
  return res.json();
}

export const api = { get: apiGet, postCommand, uploadTranscript };
