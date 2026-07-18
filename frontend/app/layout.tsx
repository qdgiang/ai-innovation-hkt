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
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
