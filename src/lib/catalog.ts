// Content categories. `key` is stored in items.category; `label` is shown.
export const CATEGORIES: { key: string; label: string }[] = [
  { key: "sermon", label: "Sermons" },
  { key: "class", label: "Classes & Studies" },
  { key: "conference", label: "Conferences" },
  { key: "open_air", label: "Open-Air Preaching" },
  { key: "podcast", label: "Be A Berean (Podcast)" },
  // Michael as a GUEST on someone else's show. Deliberately separate from
  // "podcast", which means Be A Berean — his own programme.
  { key: "interview", label: "Interviews & Guest Appearances" },
  // One-to-one evangelistic dialogue, as distinct from preaching at a crowd.
  // Every key here is a FORMAT. Topics ("abortion abolition") belong in a
  // collection, not here — mixing the two is what makes a category list rot.
  { key: "conversation", label: "Conversations" },
];

export const CATEGORY_LABEL: Record<string, string> =
  Object.fromEntries(CATEGORIES.map((c) => [c.key, c.label]));

// --- video links ------------------------------------------------------------
// items.video_url holds a bare URL and nothing else; the platform is derived
// here at render time. Adding a new host means adding a line below, not a
// migration.
const VIDEO_HOSTS: { match: RegExp; label: string; platform: string }[] = [
  { match: /(^|\.)(youtube\.com|youtu\.be)$/i, label: "Watch on YouTube", platform: "youtube" },
  { match: /(^|\.)rumble\.com$/i, label: "Watch on Rumble", platform: "rumble" },
  { match: /(^|\.)vimeo\.com$/i, label: "Watch on Vimeo", platform: "vimeo" },
  { match: /(^|\.)(facebook\.com|fb\.watch)$/i, label: "Watch on Facebook", platform: "facebook" },
  { match: /(^|\.)sermonaudio\.com$/i, label: "Watch on SermonAudio", platform: "sermonaudio" },
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

/**
 * Platform slug ("youtube", "rumble", …) or "" when the host isn't recognised.
 * Used as a CSS hook so a link can wear its platform's colour.
 */
export function videoPlatform(url: string): string {
  try {
    const host = new URL(url).hostname;
    return VIDEO_HOSTS.find((h) => h.match.test(host))?.platform ?? "";
  } catch {
    return "";
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
