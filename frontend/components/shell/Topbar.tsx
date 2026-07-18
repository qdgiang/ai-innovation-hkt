"use client";

// Persona switcher (DSH-1, "modeled, not enforced" — architecture.md §Trust
// boundaries #3) is the ONLY identity control; there is no login. Personas come
// from GET /personas (server-fetched in layout.tsx); the selection lands in the
// `evermind_persona` cookie and every page re-renders against it.
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { setPersonaCookie } from "@/lib/persona-client";
import type { Persona } from "@/lib/types";

const RANK_LABEL: Record<number, string> = { 1: "member", 2: "lead", 3: "coordinator" };

export function Topbar({
  personas,
  currentPersona,
}: {
  personas: Persona[];
  currentPersona: string;
}) {
  const router = useRouter();
  const [selected, setSelected] = useState(currentPersona);
  const [, startTransition] = useTransition();

  function onSwitch(handle: string) {
    setSelected(handle);
    setPersonaCookie(handle);
    startTransition(() => router.refresh());
  }

  const selectable = personas.filter((p) => p.handle);

  return (
    <header className="flex h-14 items-center justify-between border-b border-slate-200 px-4 dark:border-slate-800">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <span>
          Đang xem với vai trò{" "}
          <span className="font-medium text-slate-800 dark:text-slate-200">@{selected}</span>
        </span>
        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
          không xác thực — demo
        </span>
      </div>

      <select
        value={selected}
        onChange={(e) => onSwitch(e.target.value)}
        aria-label="Persona switcher"
        className="rounded-md border border-slate-200 bg-transparent px-2 py-1.5 text-sm dark:border-slate-800 dark:bg-surface-dark"
      >
        {selectable.length === 0 && <option value={selected}>{selected}</option>}
        {selectable.map((p) => (
          <option key={p.id} value={p.handle!}>
            {p.name} — {RANK_LABEL[p.role_rank] ?? p.role_rank}
            {p.status === "provisional" ? " (provisional)" : ""}
          </option>
        ))}
      </select>
    </header>
  );
}
