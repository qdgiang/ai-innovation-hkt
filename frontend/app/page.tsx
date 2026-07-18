// The knowledge-base workspace (frontend_ref shape) — the product's main
// surface. ?project=<id> switches project, ?view= picks the opening tab.
import { WorkspaceApp } from "@/components/workspace/WorkspaceApp";
import { api } from "@/lib/api-client";
import { currentPersona } from "@/lib/persona";
import type { WsBundle, WsProject } from "@/lib/workspace";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ project?: string; view?: string }>;
}) {
  const { project, view } = await searchParams;
  const persona = await currentPersona();

  let projects: WsProject[] = [];
  let bundle: WsBundle | null = null;
  try {
    projects = await api.get<WsProject[]>("/projects");
    const id = project && /^\d+$/.test(project)
      ? Number(project)
      : projects[0]?.id ?? 1;
    bundle = await api.get<WsBundle>(`/workspace/${id}`, persona);
  } catch {
    // backend not reachable — render the notice below
  }

  if (!bundle) {
    return (
      <div style={{ padding: 48, fontFamily: "Inter, sans-serif" }}>
        <h1 style={{ fontSize: 18 }}>EverMind</h1>
        <p>API chưa sẵn sàng — kiểm tra backend (http://localhost:8000/healthz) rồi tải lại trang.</p>
      </div>
    );
  }

  return (
    <WorkspaceApp
      bundle={bundle}
      projects={projects}
      personaHandle={persona}
      initialView={view}
    />
  );
}
