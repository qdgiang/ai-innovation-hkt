"use client";

// Ported from frontend_ref/index.html (sidebar nav + persona/profile row + capture
// status card) — reference design for DSH-1 (owner: B). Nav items map to the real
// dashboard views (DSH-2..8), not the frontend_ref prototype's own "knowledge base"
// concept.
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/feed", label: "Feed & Inbox", owner: "B" },
  { href: "/tasks", label: "Task board", owner: "B" },
  { href: "/decisions", label: "Decision log", owner: "A" },
  { href: "/digest", label: "Digest", owner: "B" },
  { href: "/blockers", label: "Blocker radar", owner: "B" },
  { href: "/upload", label: "Upload transcript", owner: "B" },
  { href: "/qa", label: "Ask EverMind", owner: "A" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-64 flex-col justify-between border-r border-slate-200 bg-surface-sunken p-4 dark:border-slate-800 dark:bg-surface-dark-sunken">
      <div>
        <div className="mb-6 flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-brand-coral" />
          <div>
            <div className="font-semibold leading-tight">EverMind</div>
            <div className="text-xs text-slate-500">Organizational memory</div>
          </div>
        </div>

        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const active = pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center justify-between rounded-md px-3 py-2 text-sm transition ${
                  active
                    ? "bg-brand-coral/10 font-medium text-brand-coral"
                    : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                }`}
              >
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="rounded-lg border border-slate-200 p-3 text-xs dark:border-slate-800">
        <div className="mb-1 flex items-center gap-1.5 font-medium">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          Memory capture active
        </div>
        <div className="text-slate-500">status from GET /health/capture (CAP-5)</div>
      </div>
    </aside>
  );
}
