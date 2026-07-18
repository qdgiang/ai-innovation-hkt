// DSH-5 (half), owner: B. Team digest (SRF-3). ?team=<id> selects the team;
// decisions/policy log + pending-proposals sections are TODO — they need
// `decisions` (Lane A, not built).
import { api } from "@/lib/api-client";
import type { Digest } from "@/lib/types";

export default async function DigestPage({
  searchParams,
}: {
  searchParams: Promise<{ team?: string }>;
}) {
  const { team } = await searchParams;
  const teamId = team ?? "1";

  let digest: Digest | null = null;
  try {
    digest = await api.get<Digest>(`/digest/${teamId}`);
  } catch {
    // backend not reachable
  }

  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold">Digest — team {teamId}</h1>

      {!digest && <p className="text-sm text-slate-500">No data yet.</p>}

      {digest && (
        <div className="space-y-6">
          <section>
            <h2 className="mb-2 text-sm font-medium uppercase text-slate-500">Tasks by status</h2>
            <div className="flex gap-4 text-sm">
              {Object.entries(digest.tasks_by_status).map(([status, count]) => (
                <span key={status} className="rounded-md bg-surface-sunken px-2 py-1 dark:bg-surface-dark-sunken">
                  {status}: {count}
                </span>
              ))}
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-sm font-medium uppercase text-slate-500">Blockers</h2>
            {digest.blockers.length === 0 && <p className="text-sm text-slate-400">None open.</p>}
            <ul className="space-y-1 text-sm">
              {digest.blockers.map((b) => (
                <li key={b.task_id}>
                  {b.description} — waiting on {b.waiting_on_text ?? `party #${b.waiting_on_party_id}`}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="mb-2 text-sm font-medium uppercase text-slate-500">Needs attention</h2>
            {digest.needs_attention.length === 0 && <p className="text-sm text-slate-400">Nothing flagged.</p>}
            <ul className="space-y-1 text-sm">
              {digest.needs_attention.map((e, i) => (
                <li key={i}>task #{e.task_id} — {e.lamp}</li>
              ))}
            </ul>
          </section>

          {digest.wrap_note && (
            <section>
              <h2 className="mb-2 text-sm font-medium uppercase text-slate-500">Team wrap (verbatim)</h2>
              <blockquote className="border-l-2 border-brand-coral pl-3 text-sm italic">
                “{digest.wrap_note}” — user #{digest.wrap_note_by}
              </blockquote>
            </section>
          )}

          <p className="text-xs text-slate-400">
            Decision/policy log and pending-proposal sections: owner A (needs `decisions`).
          </p>
        </div>
      )}
    </div>
  );
}
