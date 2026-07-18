// DSH-2, owner: B. Feed (SRF-1) + Inbox (SRF-2), scoped to the switcher persona.
import Link from "next/link";
import { api } from "@/lib/api-client";
import { currentPersona } from "@/lib/persona";
import type { FeedEntry, InboxItem } from "@/lib/types";

export default async function FeedPage({
  searchParams,
}: {
  searchParams: Promise<{ as?: string }>;
}) {
  // Persona comes from the Topbar switcher's cookie; `?as=<handle>` overrides
  // it for quick curl/link testing.
  const { as } = await searchParams;
  const persona = as ?? (await currentPersona());
  let feed: FeedEntry[] = [];
  let inbox: InboxItem[] = [];
  try {
    [feed, inbox] = await Promise.all([
      api.get<FeedEntry[]>("/feed", persona),
      api.get<InboxItem[]>("/inbox", persona),
    ]);
  } catch {
    // backend not reachable — render empty rather than crash the page
  }

  return (
    <div className="grid grid-cols-2 gap-6">
      <section>
        <h1 className="mb-4 text-lg font-semibold">Feed</h1>
        {feed.length === 0 && <p className="text-sm text-slate-500">No entries yet.</p>}
        <ul className="space-y-2">
          {feed.map((entry) => (
            <li key={entry.id} className="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
              <div className="flex items-center justify-between">
                <span className="font-medium">{entry.kind}</span>
                <span className="text-xs text-slate-400">{new Date(entry.ts).toLocaleString()}</span>
              </div>
              {typeof entry.payload.description === "string" && (
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                  {entry.payload.description}
                </p>
              )}
              <div className="mt-1 flex gap-3">
                {entry.decision_id != null && (
                  <Link href="/decisions" className="text-xs text-brand-coral hover:underline">
                    decision #{entry.decision_id}
                  </Link>
                )}
                {entry.task_id != null && (
                  <Link href={`/tasks/${entry.task_id}`} className="text-xs text-brand-coral hover:underline">
                    task #{entry.task_id}
                  </Link>
                )}
                {entry.superseded_by_entry != null && (
                  <span className="text-xs text-amber-600">↩ retracted</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h1 className="mb-4 text-lg font-semibold">Inbox</h1>
        {inbox.length === 0 && <p className="text-sm text-slate-500">Nothing pending.</p>}
        <ul className="space-y-2">
          {inbox.map((item) => (
            <li key={item.id} className="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
              <div className="flex items-center justify-between">
                <span className="font-medium">{item.kind}</span>
                <span className="text-xs text-slate-400">{new Date(item.created_at).toLocaleString()}</span>
              </div>
              <div className="mt-1">
                {item.kind === "proposal" || item.kind === "challenge" ? (
                  <Link href="/decisions?show_inactive=false" className="text-xs text-brand-coral hover:underline">
                    review decision #{item.ref_id} →
                  </Link>
                ) : (
                  <Link href={`/tasks/${item.ref_id}`} className="text-xs text-brand-coral hover:underline">
                    task #{item.ref_id}
                  </Link>
                )}
              </div>
              {item.resolved_at && (
                <span className="text-xs text-emerald-600">resolved: {item.resolution}</span>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
