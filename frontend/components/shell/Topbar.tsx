"use client";

// Ported from frontend_ref/index.html topbar (search trigger + persona avatar).
// Persona switcher (DSH-1, "modeled, not enforced" — architecture.md §Trust
// boundaries #3) is the ONLY identity control; there is no login.
import { useState } from "react";

const SEEDED_PERSONAS = ["linh (coordinator)", "mai (lead)", "khoa (member)"];

export function Topbar() {
  const [persona, setPersona] = useState(SEEDED_PERSONAS[0]);

  return (
    <header className="flex h-14 items-center justify-between border-b border-slate-200 px-4 dark:border-slate-800">
      <button className="flex items-center gap-2 rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-500 dark:border-slate-800">
        <span>Tìm task, decision hoặc evidence…</span>
        <kbd className="rounded bg-slate-100 px-1 text-xs dark:bg-slate-800">⌘K</kbd>
      </button>

      <select
        value={persona}
        onChange={(e) => setPersona(e.target.value)}
        aria-label="Persona switcher"
        className="rounded-md border border-slate-200 bg-transparent px-2 py-1.5 text-sm dark:border-slate-800"
      >
        {SEEDED_PERSONAS.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>
    </header>
  );
}
