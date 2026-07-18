// DSH-3, owner: B. Task board. Click a card title -> /tasks/[id] for the
// reasoning popup (log, time-travel); the per-card status select is the
// TSK-2 write lane (RecordTaskUpdate via the command gateway).
import Link from "next/link";
import { TaskStatusSelect } from "@/components/tasks/TaskStatusSelect";
import { api } from "@/lib/api-client";
import { currentPersona } from "@/lib/persona";
import type { Persona, Task, TaskStatus } from "@/lib/types";

const COLUMNS: TaskStatus[] = ["todo", "doing", "blocked", "done"];

export default async function TasksPage() {
  const persona = await currentPersona();

  let tasks: Task[] = [];
  let personas: Persona[] = [];
  try {
    [tasks, personas] = await Promise.all([
      api.get<Task[]>("/tasks", persona),
      api.get<Persona[]>("/personas"),
    ]);
  } catch {
    // backend not reachable — render an empty board rather than crash the page
  }
  const personaUserIds = Object.fromEntries(
    personas.filter((p) => p.handle).map((p) => [p.handle!, p.id]),
  );

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
                  <div
                    key={t.id}
                    className="rounded-md border border-slate-200 bg-white p-2 text-sm hover:border-brand-coral dark:border-slate-800 dark:bg-surface-dark"
                  >
                    <Link href={`/tasks/${t.id}`} className="block hover:text-brand-coral">
                      {t.description || `Task #${t.id}`}
                      {t.end_date_defaulted && (
                        <span className="ml-1 text-xs text-amber-600">· defaulted date</span>
                      )}
                    </Link>
                    {t.status === "blocked" &&
                      (t.blocked_waiting_on_text || t.blocked_waiting_on_party_id) && (
                        <p className="mt-1 text-xs text-amber-600">
                          ⏳ waiting on{" "}
                          {t.blocked_waiting_on_text ?? `party #${t.blocked_waiting_on_party_id}`}
                        </p>
                      )}
                    <div className="mt-1.5">
                      <TaskStatusSelect
                        taskId={t.id}
                        status={t.status}
                        personaUserIds={personaUserIds}
                      />
                    </div>
                  </div>
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
