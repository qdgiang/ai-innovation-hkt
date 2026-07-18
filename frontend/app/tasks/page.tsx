// DSH-3, owner: B. Task board + reasoning popup (read-only first; time-travel
// wired to GET /tasks/{id}/at once TSK-8 lands).
import { api } from "@/lib/api-client";
import type { TaskSummary } from "@/lib/types";

const COLUMNS: TaskSummary["status"][] = ["todo", "doing", "blocked", "done"];

export default async function TasksPage() {
  let tasks: TaskSummary[] = [];
  try {
    tasks = await api.get<TaskSummary[]>("/tasks");
  } catch {
    // TODO(B): backend not wired yet
  }

  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold">Task board</h1>
      <div className="grid grid-cols-4 gap-4">
        {COLUMNS.map((status) => (
          <div key={status} className="rounded-lg bg-surface-sunken p-3 dark:bg-surface-dark-sunken">
            <div className="mb-2 text-xs font-medium uppercase text-slate-500">{status}</div>
            <div className="space-y-2">
              {tasks
                .filter((t) => t.status === status)
                .map((t) => (
                  <div key={t.id} className="rounded-md border border-slate-200 bg-white p-2 text-sm dark:border-slate-800 dark:bg-surface-dark">
                    {t.description}
                  </div>
                ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
