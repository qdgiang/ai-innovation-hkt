// DSH-5 (half), owner: B. Blocker board grouped by counterparty (SIG-2):
// asserted-blocked tasks + PROMOTED weak signals (SIG-1 — voiced ≥2 times or
// 1 + staleness; the accumulated mentions are the citations, G27).
import Link from "next/link";
import { api } from "@/lib/api-client";
import type { BlockersBoard } from "@/lib/types";

export default async function BlockersPage() {
  let board: BlockersBoard = {};
  try {
    board = await api.get<BlockersBoard>("/blockers?by=party");
  } catch {
    // backend not reachable
  }

  const groups = Object.entries(board);

  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold">Blocker radar</h1>
      {groups.length === 0 && <p className="text-sm text-slate-500">No open blockers.</p>}
      <div className="space-y-4">
        {groups.map(([party, cards]) => (
          <div key={party} className="rounded-lg border border-amber-300 bg-amber-50 p-3 dark:border-amber-700 dark:bg-amber-950/30">
            <div className="mb-2 font-medium">
              {party}{" "}
              <span className="text-sm text-slate-500">
                · {cards.tasks.length + cards.signals.length} item(s)
              </span>
            </div>
            <ul className="space-y-1">
              {cards.tasks.map((t) => (
                <li key={`t${t.task_id}`} className="text-sm">
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
              {cards.signals.map((s, i) => (
                <li key={`s${i}`} className="text-sm">
                  <span className="mr-1 rounded bg-amber-200 px-1 text-xs font-medium text-amber-900 dark:bg-amber-800 dark:text-amber-100">
                    {s.mentions}× nhắc
                  </span>
                  {s.task_id != null ? (
                    <Link href={`/tasks/${s.task_id}`} className="hover:underline">
                      {s.topic}
                    </Link>
                  ) : (
                    <span>{s.topic}</span>
                  )}
                  <span className="ml-2 text-xs text-slate-500">
                    since {new Date(s.since).toLocaleDateString()} · «{s.excerpt}»
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
