/**
 * The video badge sits inside a result row's own <a href="/listen/...">.
 * Shared by index.astro (its own rows) and ResultRow.astro (search), since
 * both render the same badge markup and Astro scopes per-file <script> tags.
 * preventDefault+stopPropagation before the anchor's default action fires
 * stops the row navigation, so the badge opens video_url in a new tab instead.
 */
(() => {
  const open = (el) => {
    const url = el.dataset.videoUrl;
    if (url) window.open(url, "_blank", "noopener,noreferrer");
  };
  document.querySelectorAll("[data-video-link]").forEach((el) => {
    el.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); open(el); });
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); open(el); }
    });
  });
})();
