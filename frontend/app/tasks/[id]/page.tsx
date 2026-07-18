// DSH-3 reasoning popup: grounded summary + log (design-v2.md §Reasoning
// views). Citation badges + show-inactive (superseded/rejected decisions)
// need `decisions` (Lane A, not built yet) — the log below only carries what
// `tasks` itself tracks (its own decision-log + PIC updates), dual-stamped.
import Link from "next/link";
import { api } from "@/lib/api-client";
import type { ReasoningLogEntry, Task, TaskReasoning } from "@/lib/types";

function formatOp(op: { target: string; facet: string; op: string; value: unknown }) {
  return `${op.target} · ${op.facet} ${op.op} ${JSON.stringify(op.value)}`;
}

function LogRow({ entry }: { entry: ReasoningLogEntry }) {
  const dualStamp =
    entry.ts !== entry.recorded_at ? (
      <span className="text-slate-400"> (recorded {new Date(entry.recorded_at).toLocaleString()})</span>
    ) : null;

  if (entry.source === "decision") {
    return (
      <li className="rounded-md border border-slate-200 p-2 text-sm dark:border-slate-800">
        <div className="text-xs text-slate-500">
          {new Date(entry.ts).toLocaleString()}
          {dualStamp} · decision #{entry.decision_id}
          {entry.retracted && <span className="ml-1 text-red-500">(retracted)</span>}
        </div>
        <ul className="mt-1 list-disc pl-4">
          {entry.ops?.map((op, i) => <li key={i}>{formatOp(op)}</li>)}
        </ul>
      </li>
    );
  }

  return (
    <li className="rounded-md border border-slate-200 p-2 text-sm dark:border-slate-800">
      <div className="text-xs text-slate-500">
        {new Date(entry.ts).toLocaleString()}
        {dualStamp} · update by user #{entry.actor_user_id} ({entry.kind})
      </div>
      <div className="mt-1">{JSON.stringify(entry.payload)}</div>
    </li>
  );
}

export default async function TaskReasoningPage({
  params, searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ at?: string }>;
}) {
  const { id } = await params;
  const { at } = await searchParams;

  let reasoning: TaskReasoning | null = null;
  let atState: Record<string, unknown> | null = null;
  try {
    reasoning = await api.get<TaskReasoning>(`/tasks/${id}/reasoning`);
    if (at) {
      atState = await api.get<Record<string, unknown>>(
        `/tasks/${id}/at?ts=${encodeURIComponent(at)}`,
      );
    }
  } catch {
    // backend not reachable
  }

  const task: Task | null = reasoning?.task ?? null;

  return (
    <div>
      <Link href="/tasks" className="mb-4 inline-block text-sm text-slate-500 hover:underline">
        ← Task board
      </Link>
      <h1 className="mb-1 text-lg font-semibold">{task?.description ?? `Task #${id}`}</h1>
      <p className="mb-4 text-sm text-slate-500">
        status: {task?.status ?? "unknown"} · project {task?.project_id} ({task?.project_kind})
      </p>

      {atState && (
        <div className="mb-4 rounded-md border border-brand-coral/40 bg-brand-coral/5 p-3 text-sm">
          <strong>Time-travel @ {at}:</strong> {JSON.stringify(atState)}
        </div>
      )}

      <h2 className="mb-2 text-sm font-medium uppercase text-slate-500">Log</h2>
      <ul className="space-y-2">
        {(reasoning?.log ?? []).map((entry, i) => <LogRow key={i} entry={entry} />)}
        {(reasoning?.log ?? []).length === 0 && (
          <p className="text-sm text-slate-400">No decisions or updates recorded yet.</p>
        )}
      </ul>
    </div>
  );
}
