// DSH-4, owner: A. The decision/policy log: live GET /decisions with the filter
// matrix (q / scope / user / show_inactive) + approve/reject taps on pendings.
import Link from "next/link";
import { DecisionActions } from "@/components/decisions/DecisionActions";
import { api } from "@/lib/api-client";
import { currentPersona } from "@/lib/persona";
import type { Decision, Persona } from "@/lib/types";

const STATUS_STYLE: Record<string, string> = {
  effective: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  proposed: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  superseded: "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400",
  rejected: "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300",
};

export default async function DecisionsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; scope?: string; user?: string; show_inactive?: string }>;
}) {
  const params = await searchParams;
  const showInactive = params.show_inactive === "true";
  const persona = await currentPersona();

  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.scope) query.set("scope", params.scope);
  if (params.user) query.set("user", params.user);
  query.set("show_inactive", String(showInactive));

  let decisions: Decision[] = [];
  let personas: Persona[] = [];
  try {
    [decisions, personas] = await Promise.all([
      api.get<Decision[]>(`/decisions?${query}`, persona),
      api.get<Persona[]>("/personas"),
    ]);
  } catch {
    // backend not reachable
  }
  const personaUserIds = Object.fromEntries(
    personas.filter((p) => p.handle).map((p) => [p.handle!, p.id]),
  );

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold">Decision log</h1>
        <form className="flex items-center gap-2" method="get">
          <input
            type="text"
            name="q"
            defaultValue={params.q ?? ""}
            placeholder="Tìm quyết định…"
            className="rounded-md border border-slate-200 px-2 py-1 text-sm dark:border-slate-800 dark:bg-transparent"
          />
          <input
            type="text"
            name="user"
            defaultValue={params.user ?? ""}
            placeholder="người quyết (handle)"
            className="w-40 rounded-md border border-slate-200 px-2 py-1 text-sm dark:border-slate-800 dark:bg-transparent"
          />
          <label className="flex items-center gap-1 text-xs text-slate-500">
            <input
              type="checkbox"
              name="show_inactive"
              value="true"
              defaultChecked={showInactive}
            />
            lịch sử (superseded/rejected)
          </label>
          <button className="rounded-md bg-brand-coral px-3 py-1 text-sm font-medium text-white">
            Lọc
          </button>
        </form>
      </div>

      {decisions.length === 0 && (
        <p className="text-sm text-slate-500">Chưa có quyết định nào khớp bộ lọc.</p>
      )}

      <ul className="space-y-2">
        {decisions.map((d) => (
          <li key={d.id} className="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
            <div className="flex items-start justify-between gap-3">
              <div>
                <span className={`mr-2 rounded px-1.5 py-0.5 text-xs font-medium ${STATUS_STYLE[d.status] ?? ""}`}>
                  {d.status}
                </span>
                <span className="font-medium">D{d.id}</span> · {d.description}
              </div>
              <span className="shrink-0 text-xs text-slate-400">
                {new Date(d.ts).toLocaleDateString()}
              </span>
            </div>

            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
              <span>@{d.decided_by_handle ?? d.decided_by_user_id}</span>
              <span>{d.scope_target}</span>
              <span>{d.created_from}</span>
              {d.approval_via && <span>duyệt: {d.approval_via} bởi @{d.approved_by_handle}</span>}
              {d.effect_window && (
                <span className="text-violet-600 dark:text-violet-400">
                  hiệu lực {new Date(d.effect_window.from).toLocaleDateString()}
                  {d.effect_window.until &&
                    ` → ${new Date(d.effect_window.until).toLocaleDateString()}`}{" "}
                  (ngoại lệ có thời hạn)
                </span>
              )}
              {d.superseded_by_decision_id && (
                <span className="text-amber-600">→ thay bởi D{d.superseded_by_decision_id}</span>
              )}
              {d.rejected_reason && <span className="text-rose-500">{d.rejected_reason}</span>}
              {d.citations.map((c) => (
                <span key={`${c.message_id}-${c.kind}`} className="rounded bg-slate-100 px-1 dark:bg-slate-800">
                  m{String(c.message_id).padStart(4, "0")} · {c.kind}
                </span>
              ))}
            </div>

            {d.context && <p className="mt-1 text-xs italic text-slate-400">{d.context}</p>}

            {d.status === "proposed" && (
              <DecisionActions decisionId={d.id} personaUserIds={personaUserIds} />
            )}

            {d.ops.some((op) => op.target.startsWith("task:")) && (
              <div className="mt-1">
                <Link
                  href={`/tasks/${d.ops.find((op) => op.target.startsWith("task:"))!.target.split(":")[1]}`}
                  className="text-xs text-brand-coral hover:underline"
                >
                  → task liên quan
                </Link>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
