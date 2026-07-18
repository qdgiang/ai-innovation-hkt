// DSH-2, owner: B. Feed (SRF-1) + Inbox (SRF-2).
import { api } from "@/lib/api-client";
import type { FeedEntry, InboxItem } from "@/lib/types";

export default async function FeedPage() {
  let feed: FeedEntry[] = [];
  let inbox: InboxItem[] = [];
  try {
    [feed, inbox] = await Promise.all([
      api.get<FeedEntry[]>("/feed", "1"),
      api.get<InboxItem[]>("/inbox", "1"),
    ]);
  } catch {
    // TODO(B): backend not wired yet — P4 exit is "make demo shows real state"
  }

  return (
    <div className="grid grid-cols-2 gap-6">
      <section>
        <h1 className="mb-4 text-lg font-semibold">Feed</h1>
        {feed.length === 0 && <p className="text-sm text-slate-500">No entries yet.</p>}
        <ul className="space-y-2">
          {feed.map((entry) => (
            <li key={entry.id} className="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
              {entry.kind} — {entry.ts}
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
              {item.kind} · created {item.created_at}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
