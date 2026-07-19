// DSH-5 (half), owner: B. Blocker board grouped by party (SIG-2).
import Link from "next/link";
import { api } from "@/lib/api-client";
import { currentPersona } from "@/lib/persona";
import type { BlockersResponse } from "@/lib/types";

export default async function BlockersPage({ searchParams }: { searchParams: Promise<{ project_id?: string }> }) {
  let board: BlockersResponse = { groups: [] };
  let projects: { id: number; name?: string }[] = [];
  const selectedProject = (await searchParams).project_id;
  try {
    const persona = await currentPersona();
    projects = await api.get<{ id: number; name?: string }[]>("/projects", persona);
    const projectId = selectedProject ?? (projects.length === 1 ? String(projects[0].id) : undefined);
    if (projectId) board = await api.get<BlockersResponse>(`/blockers?project_id=${projectId}`, persona);
  } catch {
    // backend not reachable
  }

  const groups = board.groups;

  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold">Blocker radar</h1>
      {projects.length > 1 && !selectedProject && <p className="mb-3 text-sm text-slate-500">Choose a project to view its blockers.</p>}
      {projects.length > 1 && <nav className="mb-3 flex gap-2 text-sm">{projects.map((project) => <Link key={project.id} href={`/blockers?project_id=${project.id}`} className="hover:underline">{project.name ?? `Project ${project.id}`}</Link>)}</nav>}
      {groups.length === 0 && <p className="text-sm text-slate-500">No open blockers.</p>}
      <div className="space-y-4">
        {groups.map((group) => (
          <div key={`${group.waiting_on.party_id}-${group.waiting_on.text}`} className="rounded-lg border border-amber-300 bg-amber-50 p-3 dark:border-amber-700 dark:bg-amber-950/30">
            <div className="mb-2 font-medium">
              {group.waiting_on.name ?? group.waiting_on.text ?? "Unspecified"} <span className="text-sm text-slate-500">· {group.tasks.length} task(s)</span>
            </div>
            <ul className="space-y-1">
              {group.tasks.map((t) => (
                <li key={t.task_id} className="text-sm">
                  <Link href={`/tasks/${t.task_id}`} className="hover:underline">
                    {t.description}
                  </Link>
                  {t.since && (
                    <span className="ml-2 text-xs text-slate-500">
                      since {new Date(t.since).toLocaleDateString()}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
