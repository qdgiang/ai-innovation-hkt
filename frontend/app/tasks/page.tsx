// DSH-3, owner: B. Task board (read-only). Click a card -> /tasks/[id] for the
// reasoning popup (log, time-travel).
import Link from "next/link";
import { api } from "@/lib/api-client";
import type { Task, TaskStatus } from "@/lib/types";

const COLUMNS: TaskStatus[] = ["todo", "doing", "blocked", "done"];

export default async function TasksPage() {
  let tasks: Task[] = [];
  try {
    tasks = await api.get<Task[]>("/tasks");
  } catch {
    // backend not reachable — render an empty board rather than crash the page
  }

  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold">Task board</h1>
      <div className="grid grid-cols-4 gap-4">
        {COLUMNS.map((status) => (
          <div key={status} className="rounded-lg bg-surface-sunken p-3 dark:bg-surface-dark-sunken">
            <div className="mb-2 text-xs font-medium uppercase text-slate-500">
              {status} · {tasks.filter((t) => t.status === status).length}
            </div>
            <div className="space-y-2">
              {tasks
                .filter((t) => t.status === status)
                .map((t) => (
                  <Link
                    key={t.id}
                    href={`/tasks/${t.id}`}
                    className="block rounded-md border border-slate-200 bg-white p-2 text-sm hover:border-brand-coral dark:border-slate-800 dark:bg-surface-dark"
                  >
                    {t.description || `Task #${t.id}`}
                    {t.end_date_defaulted && (
                      <span className="ml-1 text-xs text-amber-600">· defaulted date</span>
                    )}
                  </Link>
                ))}
              {tasks.filter((t) => t.status === status).length === 0 && (
                <p className="text-xs text-slate-400">—</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
