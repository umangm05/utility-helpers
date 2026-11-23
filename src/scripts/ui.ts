// Site-wide UI enhancements: theme toggle, Ctrl+K command bar, recent tools,
// and the hand-off from the home "drop anything" zone to a tool page.
//
// Privacy: theme, recent-tool slugs and a dropped snippet are kept in the
// browser only (localStorage / sessionStorage). This file makes no network
// requests. Consent + usage events stay in /assets/site.js, untouched.

interface ClientTool { slug: string; name: string; icon: string; section: string; accepts: string[] }

const THEME_KEY = "uh-theme";
const RECENT_KEY = "uh-recent";
const DROP_KEY = "uh-drop";
const RECENT_MAX = 6;

const root = document.documentElement;
const tools: ClientTool[] = (() => {
  try { return JSON.parse(document.getElementById("uh-tools")?.textContent || "[]"); } catch { return []; }
})();

function lsGet(k: string): string | null { try { return localStorage.getItem(k); } catch { return null; } }
function lsSet(k: string, v: string) { try { localStorage.setItem(k, v); } catch { /* private mode */ } }


// ---- theme ---------------------------------------------------------------
function currentTheme(): "light" | "dark" {
  const set = root.getAttribute("data-theme");
  if (set === "light" || set === "dark") return set;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
document.querySelectorAll<HTMLButtonElement>(".theme-toggle").forEach((btn) => {
  const label = () => btn.setAttribute("aria-label", currentTheme() === "dark" ? "Switch to light theme" : "Switch to dark theme");
  label();
  btn.addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    lsSet(THEME_KEY, next);
    label();
  });
});

// ---- recent tools ----------------------------------------------------------
export function recentSlugs(): string[] {
  try {
    const v = JSON.parse(lsGet(RECENT_KEY) || "[]");
    return Array.isArray(v) ? v.filter((s) => tools.some((t) => t.slug === s)).slice(0, RECENT_MAX) : [];
  } catch { return []; }
}
const toolSlug = document.getElementById("main")?.getAttribute("data-uh-tool");
// "Reject" promises that only the choice itself is stored, so no recents then.
const rejected = lsGet("uh-consent") === "reject";
if (rejected) { try { localStorage.removeItem(RECENT_KEY); } catch { /* ignore */ } }
if (toolSlug) {
  if (!rejected) {
    lsSet(RECENT_KEY, JSON.stringify([toolSlug, ...recentSlugs().filter((s) => s !== toolSlug)].slice(0, RECENT_MAX)));
  }

  // Text handed over from the home drop zone (same tab, never sent anywhere).
  try {
    const raw = sessionStorage.getItem(DROP_KEY);
    if (raw) {
      sessionStorage.removeItem(DROP_KEY);
      const drop = JSON.parse(raw) as { slug: string; text: string };
      const field = document.querySelector<HTMLTextAreaElement | HTMLInputElement>(
        "#main .tool textarea:not([readonly]), #main .tool input[type=text]:not([readonly])");
      if (drop.slug === toolSlug && field && typeof drop.text === "string") {
        field.value = drop.text;
        field.dispatchEvent(new Event("input", { bubbles: true }));
        field.focus();
      }
    }
  } catch { /* storage unavailable */ }
}

// ---- command bar (Ctrl+K / Cmd+K / "/") ------------------------------------
const dlg = document.getElementById("uh-cmd") as HTMLDialogElement | null;
const input = document.getElementById("uh-cmd-input") as HTMLInputElement | null;
const list = document.getElementById("uh-cmd-list") as HTMLUListElement | null;
const empty = dlg?.querySelector<HTMLElement>(".cmd-empty") ?? null;
let active = 0;
let shown: ClientTool[] = [];

function score(t: ClientTool, q: string): number {
  const name = t.name.toLowerCase();
  if (!q) return 1;
  if (name.startsWith(q)) return 3;
  if (name.includes(q)) return 2;
  // loose subsequence match ("jsf" -> "JSON Formatter")
  let i = 0;
  for (const ch of name) if (ch === q[i]) i++;
  return i === q.length ? 1 : 0;
}

function render() {
  if (!list || !input) return;
  const q = input.value.trim().toLowerCase();
  const recent = recentSlugs();
  shown = tools
    .map((t) => ({ t, s: score(t, q) + (!q && recent.includes(t.slug) ? 10 - recent.indexOf(t.slug) : 0) }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s)
    .map((x) => x.t);
  active = Math.min(active, Math.max(shown.length - 1, 0));
  list.replaceChildren(...shown.map((t, i) => {
    const li = document.createElement("li");
    li.id = `uh-cmd-opt-${t.slug}`;
    li.setAttribute("role", "option");
    li.setAttribute("aria-selected", String(i === active));
    const a = document.createElement("a");
    a.href = `/${t.slug}/`;
    a.tabIndex = -1;
    a.textContent = t.name;
    const meta = document.createElement("span");
    meta.className = "cmd-meta";
    meta.textContent = recent.includes(t.slug) && !q ? "Recent" : t.section;
    a.append(meta);
    li.append(a);
    li.addEventListener("mousemove", () => { if (active !== i) { active = i; paint(); } });
    return li;
  }));
  if (empty) empty.hidden = shown.length > 0;
  paint();
}
function paint() {
  if (!list || !input) return;
  [...list.children].forEach((li, i) => li.setAttribute("aria-selected", String(i === active)));
  const cur = shown[active];
  if (cur) {
    input.setAttribute("aria-activedescendant", `uh-cmd-opt-${cur.slug}`);
    document.getElementById(`uh-cmd-opt-${cur.slug}`)?.scrollIntoView({ block: "nearest" });
  } else input.removeAttribute("aria-activedescendant");
}
function openCmd() {
  if (!dlg || !input || dlg.open) return;
  input.value = "";
  active = 0;
  render();
  dlg.showModal();
  input.focus();
}
document.querySelectorAll(".cmd-open").forEach((b) => b.addEventListener("click", openCmd));
document.addEventListener("keydown", (e) => {
  const typing = e.target instanceof HTMLElement && e.target.closest("input, textarea, select, [contenteditable]");
  if ((e.key === "k" || e.key === "K") && (e.ctrlKey || e.metaKey)) { e.preventDefault(); openCmd(); }
  else if (e.key === "/" && !typing && !dlg?.open) { e.preventDefault(); openCmd(); }
});
input?.addEventListener("input", () => { active = 0; render(); });
input?.addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown") { e.preventDefault(); active = Math.min(active + 1, shown.length - 1); paint(); }
  else if (e.key === "ArrowUp") { e.preventDefault(); active = Math.max(active - 1, 0); paint(); }
  else if (e.key === "Enter" && shown[active]) { e.preventDefault(); location.href = `/${shown[active].slug}/`; }
});
// Click on the backdrop closes the dialog.
dlg?.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });

// ---- offline / installable (PWA) ----------------------------------------------
// The worker (/sw.js, generated by scripts/gen-sw.mjs) caches this site's own pages and
// files so every tool keeps working offline after the first visit. Registered after load
// so it never competes with the page itself.
if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
  window.addEventListener("load", () => { navigator.serviceWorker.register("/sw.js").catch(() => { /* unsupported / blocked */ }); });
}

export { tools };
