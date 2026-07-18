// SVG icon set ported 1:1 from frontend_ref/app.js `icon()`.
const PATHS: Record<string, string> = {
  task: "M6 4h12v16H6zM9 8h6M9 12h6M9 16h4",
  decision: "M12 3v18M5 8h14M7 16h10",
  evidence: "M7 3h10v18H7zM10 8h4M10 12h4M10 16h3",
  clock: "M12 8v5l3 2",
  user: "M6 20c.5-4 2.5-6 6-6s5.5 2 6 6",
  message: "M5 5h14v11H9l-4 3V5Z",
  arrow: "M5 12h14M14 7l5 5-5 5",
  chevron: "m9 18 6-6-6-6",
  dependency: "M5 7h7v10h7M16 14l3 3-3 3",
  check: "m5 12 4 4L19 6",
  close: "m6 6 12 12M18 6 6 18",
  external: "M14 4h6v6M20 4l-9 9M18 13v6H5V6h6",
  telegram: "m20 4-3 16-5-5-3 3-1-5-5-2 17-7ZM8 13l8-5",
  link: "M10 13a4 4 0 0 0 5.7.1l2.2-2.2a4 4 0 0 0-5.7-5.7L11 6.4M14 11a4 4 0 0 0-5.7-.1l-2.2 2.2a4 4 0 0 0 5.7 5.7l1.2-1.2",
  search: "m16 16 4 4",
  bell: "M18 9a6 6 0 0 0-12 0c0 7-3 7-3 7h18s-3 0-3-7M10 20h4",
  radar: "M12 4v8l5 3",
  grid: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
  graph: "M8 7l8 0M7 8l1 8M10 17l7-8",
  help: "M9.8 9a2.4 2.4 0 1 1 3.5 2.1c-.9.5-1.3 1-1.3 2M12 17h.01",
  more: "",
};

const CIRCLES: Record<string, [number, number, number][]> = {
  clock: [[12, 12, 8]],
  user: [[12, 8, 3]],
  search: [[11, 11, 7]],
  radar: [[12, 12, 8]],
  graph: [[6, 6, 2], [18, 7, 2], [8, 18, 2]],
  help: [[12, 12, 9]],
  more: [[5, 12, 1], [12, 12, 1], [19, 12, 1]],
};

export function Icon({ name }: { name: string }) {
  const d = PATHS[name] ?? PATHS.task;
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {(CIRCLES[name] ?? []).map(([cx, cy, r]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={r} />
      ))}
      {d && <path d={d} />}
    </svg>
  );
}
