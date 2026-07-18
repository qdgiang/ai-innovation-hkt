"use client";

// CAP-3 upload flow (DSH-8-adjacent), owner: B. Uploads a meeting transcript
// (.txt/.md, EVM-011) via POST /uploads/transcript. Window flush + linkage is
// `ingestion`'s job (Lane A, not built) — this only confirms the file landed.
import { useState } from "react";
import { api } from "@/lib/api-client";
import { personaFromDocument } from "@/lib/persona-client";

export default function UploadPage() {
  const [status, setStatus] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const input = (e.currentTarget.elements.namedItem("file") as HTMLInputElement);
    const file = input.files?.[0];
    if (!file) return;
    setStatus("Uploading…");
    try {
      const result = await api.uploadTranscript(file, personaFromDocument());
      setStatus(`Uploaded — upload_id ${result.upload_id}`);
    } catch (err) {
      setStatus(`Failed: ${(err as Error).message}`);
    }
  }

  return (
    <div className="max-w-md">
      <h1 className="mb-4 text-lg font-semibold">Upload transcript</h1>
      <p className="mb-4 text-sm text-slate-500">
        .txt / .md only (EVM-011). Re-uploading the same filename creates a new
        version — it never overwrites.
      </p>
      <form onSubmit={onSubmit} className="space-y-3">
        <input type="file" name="file" accept=".txt,.md" required className="text-sm" />
        <button
          type="submit"
          className="rounded-md bg-brand-coral px-4 py-1.5 text-sm font-medium text-white"
        >
          Upload
        </button>
      </form>
      {status && <p className="mt-3 text-sm">{status}</p>}
    </div>
  );
}
