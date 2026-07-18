// DSH-5 (half), owner: B. Team digest (SRF-3).
export default function DigestPage() {
  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold">Digest</h1>
      <p className="text-sm text-slate-500">
        TODO(B): pick a team, call GET /digest/{"{team}"}?week=… (SRF-3) — sections:
        decisions, blockers by party, at-risk/overdue, pending proposals, corrections first.
      </p>
    </div>
  );
}
