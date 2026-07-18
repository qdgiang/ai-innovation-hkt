// Persona plumbing (DSH-1). The switcher writes a plain cookie; server pages
// read it with `currentPersona()` and thread it into every API call, client
// components read it with `personaFromDocument()`. "Modeled, not enforced" —
// there is no login (architecture.md §Trust boundaries #3).
import { cookies } from "next/headers";

export const PERSONA_COOKIE = "evermind_persona";
export const DEFAULT_PERSONA = "linh";
// wire-compat alias (PR #45 pages import this name)
export const DEFAULT_PERSONA_HANDLE = DEFAULT_PERSONA;

export async function currentPersona(): Promise<string> {
  const jar = await cookies();
  return jar.get(PERSONA_COOKIE)?.value ?? DEFAULT_PERSONA;
}
