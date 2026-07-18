// DSH-5, owner: B. Team digest (SRF-3). ?team=<id> selects the team;
// decisions/policy + pending-proposal sections ride on GET /decisions.
import Link from "next/link";
import { api } from "@/lib/api-client";
import { currentPersona } from "@/lib/persona";
import type { Decision, Digest } from "@/lib/types";

function daysAgo(ts: string): string {
  const days = Math.max(0, Math.floor((Date.now() - new Date(ts).getTime()) / 86_400_000));
  if (days === 0) return "hôm nay";
  return `${days} ngày trước`;
}

export default async function DigestPage({
  searchParams,
}: {
  searchParams: Promise<{ team?: string }>;
}) {
  const { team } = await searchParams;
  const teamId = team ?? "1";
  const persona = await currentPersona();

  let digest: Digest | null = null;
  let decisions: Decision[] = [];
  try {
    [digest, decisions] = await Promise.all([
      api.get<Digest>(`/digest/${teamId}`, persona),
      api.get<Decision[]>("/decisions?show_inactive=false", persona),
    ]);
  } catch {
    // backend not reachable
  }

  // Demo posture: recent effective decisions (windowed exceptions flagged)
  // rather than a strict per-team scope filter.
  const effective = decisions.filter((d) => d.status === "effective").slice(0, 6);
  const proposed = decisions.filter((d) => d.status === "proposed");

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
            <h2 className="mb-2 text-sm font-medium uppercase text-slate-500">
              Quyết định &amp; chính sách
            </h2>
            {effective.length === 0 && (
              <p className="text-sm text-slate-400">Chưa có quyết định hiệu lực.</p>
            )}
            <ul className="space-y-1 text-sm">
              {effective.map((d) => (
                <li key={d.id}>
                  <Link href="/decisions" className="hover:text-brand-coral">
                    <span className="font-medium">D{d.id}</span> · {d.description}
                  </Link>{" "}
                  <span className="text-xs text-slate-400">
                    @{d.decided_by_handle ?? d.decided_by_user_id} · {daysAgo(d.ts)}
                  </span>
                  {d.effect_window && (
                    <span className="ml-1 text-xs text-violet-600 dark:text-violet-400">
                      ngoại lệ có thời hạn{" "}
                      {new Date(d.effect_window.from).toLocaleDateString()}
                      {d.effect_window.until &&
                        ` → ${new Date(d.effect_window.until).toLocaleDateString()}`}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="mb-2 text-sm font-medium uppercase text-slate-500">Đang chờ duyệt</h2>
            {proposed.length === 0 && (
              <p className="text-sm text-slate-400">Không có đề xuất nào đang chờ.</p>
            )}
            <ul className="space-y-1 text-sm">
              {proposed.map((d) => (
                <li key={d.id}>
                  <Link href="/decisions" className="hover:text-brand-coral">
                    <span className="font-medium">D{d.id}</span> · {d.description}
                  </Link>{" "}
                  <span className="text-xs text-amber-600">
                    chờ {daysAgo(d.ts)} · @{d.decided_by_handle ?? d.decided_by_user_id}
                  </span>
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
        </div>
      )}
    </div>
  );
}
