"use client";

// DSH-7: the approve/reject taps on a pending proposal — typed commands through
// POST /commands, acting as the switcher persona. The gateway does the real
// gatekeeping (authority, revalidation); we just render its outcome honestly.
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { personaFromDocument } from "@/lib/persona-client";

export function DecisionActions({
  decisionId,
  personaUserIds,
}: {
  decisionId: number;
  personaUserIds: Record<string, number>;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function act(action: "approve" | "reject") {
    const persona = personaFromDocument();
    const personaUserId = personaUserIds[persona];
    if (personaUserId === undefined) {
      setNote(`persona @${persona} không hợp lệ`);
      return;
    }
    setBusy(true);
    setNote(null);
    try {
      const outcome =
        action === "approve"
          ? await api.approveProposal(persona, personaUserId, decisionId)
          : await api.rejectProposal(persona, personaUserId, decisionId);
      setNote(outcome.status);
      router.refresh();
    } catch (err) {
      setNote((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-2 flex items-center gap-2">
      <button
        onClick={() => act("approve")}
        disabled={busy}
        className="rounded-md bg-emerald-600 px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
      >
        Approve
      </button>
      <button
        onClick={() => act("reject")}
        disabled={busy}
        className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
      >
        Dismiss
      </button>
      {note && <span className="text-xs text-slate-500">→ {note}</span>}
    </div>
  );
}
