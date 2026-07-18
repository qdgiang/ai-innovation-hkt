import type { Metadata } from "next";
import "./globals.css";
import "./workspace.css";

export const metadata: Metadata = {
  title: "EverMind — Organizational memory",
  description: "Project knowledge base: tasks, decisions, evidence receipts",
};

// The workspace page renders its own app-shell (sidebar/topbar) in the
// frontend_ref design; legacy routes (/feed, /digest, /upload, …) are kept
// routable but are no longer part of the navigation.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  // suppressHydrationWarning is attribute-scoped (not deep): browser
  // extensions (CocCoc, Grammarly, password managers) stamp attributes onto
  // <html>/<body> before React hydrates, which is noise, not a bug of ours.
  return (
    <html lang="vi" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
