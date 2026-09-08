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

// --- video links ------------------------------------------------------------
// items.video_url holds a bare URL and nothing else; the platform is derived
// here at render time. Adding a new host means adding a line below, not a
// migration.
const VIDEO_HOSTS: { match: RegExp; label: string }[] = [
  { match: /(^|\.)(youtube\.com|youtu\.be)$/i, label: "Watch on YouTube" },
  { match: /(^|\.)rumble\.com$/i, label: "Watch on Rumble" },
  { match: /(^|\.)vimeo\.com$/i, label: "Watch on Vimeo" },
  { match: /(^|\.)(facebook\.com|fb\.watch)$/i, label: "Watch on Facebook" },
  { match: /(^|\.)sermonaudio\.com$/i, label: "Watch on SermonAudio" },
];

/**
 * Returns the URL only if it is a well-formed http(s) link, else null.
 * These are pasted in by hand, so the scheme check is load-bearing: an
 * unvalidated value goes straight into an href, and `javascript:...` there
 * would be an XSS hole.
 */
export function safeHttpUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url.trim());
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}

/** Button label for a video link — named when we recognise the host. */
export function videoLabel(url: string): string {
  try {
    const host = new URL(url).hostname;
    return VIDEO_HOSTS.find((h) => h.match.test(host))?.label ?? "Watch video";
  } catch {
    return "Watch video";
  }
}

/** "1.2 MB" — shown next to a download so the size isn't a surprise on mobile. */
export function fmtBytes(n: number | null | undefined): string {
  if (!n || n < 0) return "";
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`;
}

export function fmtDate(d: string | null | undefined): string {
  if (!d) return "";
  const dt = new Date(d + "T00:00:00");
  return isNaN(+dt) ? d : dt.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}
