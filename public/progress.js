/**
 * Listening progress — resume position and a "listened" mark, per browser.
 *
 * Deliberately NOT part of sermon-player.js: that component is shared with the
 * other audio sites (lbc, confession, jdhall), and this behaviour is ours. It
 * hooks the player's public `_audio` handle instead of being built into it.
 *
 * Everything lives in localStorage and never leaves the browser: no account, no
 * server, nothing to sync and nothing to leak. The cost is that it is per
 * browser and per device, which the UI says out loud rather than implying an
 * account exists.
 *
 * Shape:  { "<slug>": { t: seconds, d: duration, done: 1|0, at: epoch_ms } }
 */
(() => {
  const KEY = "macaudio:progress:v1";
  const HIDE_KEY = "macaudio:hide-listened";
  const DONE_FRACTION = 0.9;   // far enough in to count, early enough to skip the closing prayer
  const RESUME_MIN = 30;       // don't bother resuming the first few seconds
  const SAVE_EVERY = 8000;     // ms between writes while playing

  const load = () => {
    try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch { return {}; }
  };
  const save = (all) => {
    try { localStorage.setItem(KEY, JSON.stringify(all)); } catch {}
  };
  const fmt = (sec) => {
    if (!isFinite(sec) || sec < 0) sec = 0;
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.floor(sec % 60);
    return (h ? h + ":" + String(m).padStart(2, "0") : String(m)) + ":" + String(s).padStart(2, "0");
  };

  /* ---------------- listen page ---------------- */

  function initListen() {
    const m = location.pathname.match(/\/listen\/([^/?#]+)/);
    if (!m) return null;
    const slug = decodeURIComponent(m[1]);
    const host = document.querySelector("sermon-player");
    const actions = document.querySelector(".player .actions");
    if (!actions) return null;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-outline btn-sm";
    // Said plainly rather than behind a consent banner: nothing leaves the
    // browser, so there is nothing to consent to -- but people should still
    // know it will not follow them to another device.
    btn.title = "Remembered in this browser only";
    actions.appendChild(btn);

    const note = document.createElement("p");
    note.className = "progress-note";
    note.hidden = true;
    (document.querySelector(".player") || actions).appendChild(note);

    const paintBtn = () => {
      const done = (load()[slug] || {}).done;
      btn.textContent = done ? "✓ Listened — mark unlistened" : "Mark as listened";
      btn.setAttribute("aria-pressed", done ? "true" : "false");
    };

    btn.addEventListener("click", () => {
      const all = load();
      const rec = all[slug] || {};
      rec.done = rec.done ? 0 : 1;
      rec.at = Date.now();
      if (rec.done) { note.hidden = true; }
      all[slug] = rec;
      save(all);
      paintBtn();
    });
    paintBtn();

    if (!host) return slug;

    // The component sets _audio in connectedCallback; it may not exist yet.
    const whenReady = (cb, tries = 60) => {
      if (host._audio) return cb(host._audio);
      if (tries <= 0) return;
      setTimeout(() => whenReady(cb, tries - 1), 50);
    };

    whenReady((audio) => {
      let lastWrite = 0;
      let restored = false;

      const write = (force) => {
        const d = audio.duration, t = audio.currentTime;
        if (!isFinite(d) || d <= 0) return;
        // Never save a position from the very start. write() also runs on
        // pagehide, so opening a sermon and leaving without pressing play would
        // otherwise overwrite a real saved position with 0.
        if (t < RESUME_MIN) return;
        const now = Date.now();
        if (!force && now - lastWrite < SAVE_EVERY) return;
        lastWrite = now;
        const all = load();
        const rec = all[slug] || {};
        rec.t = Math.floor(t);
        rec.d = Math.floor(d);
        rec.at = now;
        if (t / d >= DONE_FRACTION) rec.done = 1;
        all[slug] = rec;
        save(all);
        if (rec.done) paintBtn();
      };

      const restore = () => {
        if (restored) return;
        const rec = load()[slug];
        if (!rec || rec.done) { restored = true; return; }
        // Duration may still be NaN on the first call. Bail WITHOUT latching, or
        // the later loadedmetadata call finds the flag already set and the
        // position is never restored.
        const d = audio.duration;
        if (!isFinite(d) || d <= 0) return;
        restored = true;
        if (!rec.t || rec.t < RESUME_MIN || rec.t > d * DONE_FRACTION) return;
        audio.currentTime = rec.t;
        audio.dispatchEvent(new Event("timeupdate"));
        note.hidden = false;
        note.innerHTML = "";
        note.append("Picking up where you left off — " + fmt(rec.t) + ". ");
        const a = document.createElement("button");
        a.type = "button";
        a.className = "linkish";
        a.textContent = "Start from the beginning";
        a.addEventListener("click", () => {
          audio.currentTime = 0;
          audio.dispatchEvent(new Event("timeupdate"));
          note.hidden = true;
          write(true);
        });
        note.appendChild(a);
      };

      if (audio.readyState >= 1) restore();
      audio.addEventListener("loadedmetadata", restore);
      audio.addEventListener("timeupdate", () => write(false));
      audio.addEventListener("pause", () => write(true));
      audio.addEventListener("ended", () => {
        const all = load();
        all[slug] = { ...(all[slug] || {}), done: 1, t: 0, at: Date.now() };
        save(all);
        paintBtn();
      });
      window.addEventListener("pagehide", () => write(true));
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden") write(true);
      });
    });

    return slug;
  }

  /* ---------------- library / search ---------------- */

  function initList() {
    const rows = document.querySelectorAll("[data-slug]");
    if (!rows.length) return;
    const all = load();
    let listened = 0;

    rows.forEach((row) => {
      const rec = all[row.dataset.slug];
      if (!rec || !rec.done) return;
      listened++;
      row.dataset.listened = "1";
      const tags = row.querySelector(".row-tags");
      if (tags && !tags.querySelector(".badge-listened")) {
        const b = document.createElement("span");
        b.className = "badge badge-listened";
        b.textContent = "✓ listened";
        tags.appendChild(b);
      }
    });

    const box = document.querySelector("[data-hide-listened]");
    if (!box) return;
    // The control ships hidden so a first-time visitor never sees a filter for
    // something they have none of; it has to be un-hidden once they do.
    const wrap = box.closest(".hide-listened");
    if (!listened) { wrap?.setAttribute("hidden", ""); return; }
    wrap?.removeAttribute("hidden");

    const countEl = document.querySelector("[data-result-count]");
    const total = rows.length;
    const apply = () => {
      const hide = box.checked;
      rows.forEach((r) => { r.hidden = hide && r.dataset.listened === "1"; });
      if (countEl) {
        const shown = hide ? total - listened : total;
        countEl.textContent = shown + (shown === 1 ? " item" : " items") +
          (hide ? " · " + listened + " listened hidden" : "");
      }
      try { localStorage.setItem(HIDE_KEY, hide ? "1" : "0"); } catch {}
    };

    try { box.checked = localStorage.getItem(HIDE_KEY) === "1"; } catch {}
    box.addEventListener("change", apply);
    apply();
  }

  const start = () => { initListen(); initList(); };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
