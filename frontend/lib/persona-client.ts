"use client";

// Client half of the persona plumbing — see lib/persona.ts (server half).
// Kept separate because `next/headers` may not be imported from client code.
export const PERSONA_COOKIE = "evermind_persona";
export const DEFAULT_PERSONA = "linh";

export function personaFromDocument(): string {
  if (typeof document === "undefined") return DEFAULT_PERSONA;
  const match = document.cookie.match(new RegExp(`(?:^|; )${PERSONA_COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : DEFAULT_PERSONA;
}

export function setPersonaCookie(handle: string): void {
  document.cookie = `${PERSONA_COOKIE}=${encodeURIComponent(handle)}; path=/; max-age=31536000`;
}
