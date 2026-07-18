"use client";

// TSK-2 write lane from the board: a status change is a RecordTaskUpdate
// command — PIC auto-applies, authority applies, anyone else produces a
// confirm card for the PICs (the gateway routes it; we surface the outcome).
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { personaFromDocument } from "@/lib/persona-client";
import type { TaskStatus } from "@/lib/types";

const CHOICES: TaskStatus[] = ["todo", "doing", "blocked", "done"];

export function TaskStatusSelect({
  taskId,
  status,
  personaUserIds,
}: {
  taskId: number;
  status: TaskStatus;
  personaUserIds: Record<string, number>;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function onChange(next: string) {
    const persona = personaFromDocument();
    const personaUserId = personaUserIds[persona];
    if (personaUserId === undefined || next === status) return;
    setBusy(true);
    setNote(null);
    try {
      const outcome = await api.recordTaskStatus(persona, personaUserId, taskId, next);
      setNote(outcome.status === "applied" ? null : outcome.status);
      router.refresh();
    } catch (err) {
      setNote((err as Error).message.slice(0, 80));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span onClick={(e) => e.preventDefault()} className="flex items-center gap-1">
      <select
        value={status}
        disabled={busy}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-slate-200 bg-transparent px-1 py-0.5 text-xs text-slate-500 dark:border-slate-700"
        aria-label={`status of task ${taskId}`}
      >
        {CHOICES.concat(CHOICES.includes(status) ? [] : [status]).map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
      {note && <span className="text-[10px] text-amber-600">{note}</span>}
    </span>
  );
}
