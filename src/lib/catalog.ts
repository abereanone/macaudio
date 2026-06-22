// Content categories. `key` is stored in items.category; `label` is shown.
export const CATEGORIES: { key: string; label: string }[] = [
  { key: "sermon", label: "Sermons" },
  { key: "class", label: "Classes & Studies" },
  { key: "conference", label: "Conferences" },
  { key: "open_air", label: "Open-Air Preaching" },
  { key: "podcast", label: "Be A Berean (Podcast)" },
];

export const CATEGORY_LABEL: Record<string, string> =
  Object.fromEntries(CATEGORIES.map((c) => [c.key, c.label]));

export function fmtDate(d: string | null | undefined): string {
  if (!d) return "";
  const dt = new Date(d + "T00:00:00");
  return isNaN(+dt) ? d : dt.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}
