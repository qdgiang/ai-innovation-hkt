// DSH-5 (half), owner: B. Blocker board grouped by party (SIG-2).
import { api } from "@/lib/api-client";

export default async function BlockersPage() {
  let blockers: unknown[] = [];
  try {
    blockers = await api.get<unknown[]>("/blockers?by=party");
  } catch {
    // TODO(B): backend not wired yet
  }

  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold">Blocker radar</h1>
      {blockers.length === 0 && (
        <p className="text-sm text-slate-500">No open blockers — or backend not wired yet.</p>
      )}
    </div>
  );
}
