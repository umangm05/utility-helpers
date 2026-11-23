// Spin the wheel / random picker / dice UI. Everything is local to this tab.
import { byId } from "./common";
import { tabs } from "./tabs";
import { randInt, between, pick, teams, roll, shuffle, entries } from "./random";
import { play, wireToggles } from "./sfx";

const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---- wheel -------------------------------------------------------------------
const canvas = byId<HTMLCanvasElement>("sw-canvas");
const list = byId<HTMLTextAreaElement>("sw-list");
const spinBtn = byId<HTMLButtonElement>("sw-spin");
const result = byId("sw-result");
const removeBtn = byId<HTMLButtonElement>("sw-remove");
const COLORS = ["#f59e0b", "#38bdf8", "#f472b6", "#4ade80", "#a78bfa", "#fb923c", "#2dd4bf", "#facc15", "#f87171", "#60a5fa"];
const TAU = Math.PI * 2;
let angle = 0;          // current rotation, radians clockwise
let spinning = false;
let winner = "";

const items = () => { const e = entries(list.value); return e.length ? e : ["Add some names"]; };

function draw() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const size = canvas.clientWidth || 340;
  if (canvas.width !== Math.round(size * dpr)) { canvas.width = Math.round(size * dpr); canvas.height = canvas.width; }
  const g = canvas.getContext("2d")!;
  const r = canvas.width / 2;
  const xs = items();
  const seg = TAU / xs.length;
  g.clearRect(0, 0, canvas.width, canvas.height);
  g.save();
  g.translate(r, r);
  xs.forEach((name, i) => {
    const a0 = -Math.PI / 2 + angle + i * seg;
    g.beginPath();
    g.moveTo(0, 0);
    g.arc(0, 0, r - 4 * dpr, a0, a0 + seg);
    g.closePath();
    // Odd count: avoid the first and last slice sharing a colour.
    g.fillStyle = COLORS[(xs.length % COLORS.length === 1 && i === xs.length - 1 ? 1 : i) % COLORS.length];
    g.fill();
    g.strokeStyle = "rgba(0,0,0,.15)";
    g.lineWidth = dpr;
    g.stroke();
    g.save();
    g.rotate(a0 + seg / 2);
    g.fillStyle = "#111";
    const fs = Math.max(10, Math.min(18, 260 / Math.max(6, xs.length))) * dpr;
    g.font = `600 ${fs}px system-ui, sans-serif`;
    g.textAlign = "right";
    g.textBaseline = "middle";
    const label = name.length > 18 ? `${name.slice(0, 17)}…` : name;
    g.fillText(label, r - 16 * dpr, 0);
    g.restore();
  });
  g.restore();
  canvas.setAttribute("aria-label", `Wheel with ${xs.length} options: ${xs.slice(0, 20).join(", ")}${xs.length > 20 ? "…" : ""}`);
}

/** Index of the slice under the top pointer for rotation `a`. */
const under = (a: number, n: number) => Math.floor((((-a) % TAU) + TAU) % TAU / (TAU / n)) % n;

function spin() {
  if (spinning) return;
  const xs = entries(list.value);
  if (!xs.length) { result.textContent = "Add at least one name to the list."; result.dataset.kind = "error"; return; }
  spinning = true;
  spinBtn.disabled = true;
  removeBtn.hidden = true;
  result.dataset.kind = "info";
  result.textContent = "Spinning…";
  const n = xs.length, seg = TAU / n;
  const w = randInt(n);
  // Land somewhere inside the winning slice, never on an edge.
  const offset = (0.15 + 0.7 * (randInt(1000) / 1000)) * seg;
  const desired = ((TAU - (w * seg + offset)) % TAU + TAU) % TAU;
  const start = angle;
  let end = start - (start % TAU) + desired + TAU * (reduced ? 1 : 5);
  if (end - start < TAU * (reduced ? 1 : 4)) end += TAU;
  const ms = reduced ? 600 : 4200;
  const t0 = performance.now();
  let last = under(start, n), lastTick = 0;
  const frame = (now: number) => {
    const p = Math.min(1, (now - t0) / ms);
    const e = 1 - (1 - p) ** 4;            // ease-out quart
    angle = start + (end - start) * e;
    draw();
    const cur = under(angle, n);
    if (cur !== last && now - lastTick > 45) { play("press", 1.5); lastTick = now; }
    last = cur;
    if (p < 1) { requestAnimationFrame(frame); return; }
    angle = end % TAU;
    draw();
    winner = xs[under(angle, n)];
    spinning = false;
    spinBtn.disabled = false;
    result.replaceChildren("Winner: ", Object.assign(document.createElement("strong"), { textContent: winner }));
    result.dataset.kind = "ok";
    result.dataset.winner = winner;
    removeBtn.hidden = n < 2;
    removeBtn.textContent = `Remove “${winner.length > 20 ? winner.slice(0, 19) + "…" : winner}”`;
    play("achievement");
  };
  requestAnimationFrame(frame);
}

spinBtn.addEventListener("click", spin);
canvas.addEventListener("click", spin);
list.addEventListener("input", () => { if (!spinning) draw(); });
removeBtn.addEventListener("click", () => {
  const xs = entries(list.value);
  const i = xs.indexOf(winner);
  if (i >= 0) xs.splice(i, 1);
  list.value = xs.join("\n");
  removeBtn.hidden = true;
  result.textContent = `Removed ${winner}. ${xs.length} left.`;
  draw();
});
byId("sw-shuffle").addEventListener("click", () => { list.value = shuffle(entries(list.value)).join("\n"); draw(); });
window.addEventListener("resize", () => { if (!spinning) draw(); });

// ---- picker ------------------------------------------------------------------
const mode = byId<HTMLSelectElement>("pk-mode");
const out = byId("pk-out");
const chip = (t: string, cls = "chip") => Object.assign(document.createElement("span"), { className: cls, textContent: t });
mode.addEventListener("change", () => {
  document.querySelectorAll<HTMLElement>("[data-pk]").forEach((el) => { el.hidden = !el.dataset.pk!.split(" ").includes(mode.value); });
  byId("pk-n").previousElementSibling!.textContent = mode.value === "teams" ? "How many teams?" : "How many?";
  out.replaceChildren();
});
byId("pk-go").addEventListener("click", () => {
  const n = Math.max(1, Math.round(Number(byId<HTMLInputElement>("pk-n").value) || 1));
  const xs = entries(byId<HTMLTextAreaElement>("pk-list").value);
  out.replaceChildren();
  delete out.dataset.kind;
  if (mode.value === "number") {
    let lo = Math.round(Number(byId<HTMLInputElement>("pk-min").value)), hi = Math.round(Number(byId<HTMLInputElement>("pk-max").value));
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) { out.append("Enter two whole numbers."); return; }
    if (lo > hi) [lo, hi] = [hi, lo];
    const v = between(lo, hi);
    out.append(chip(String(v), "big"));
    out.dataset.value = String(v);
  } else if (!xs.length) {
    out.append("Add some names to the list first.");
    return;
  } else if (mode.value === "teams") {
    teams(xs, n).forEach((t, i) => {
      const d = document.createElement("div");
      d.className = "team";
      d.append(Object.assign(document.createElement("b"), { textContent: `Team ${i + 1} (${t.length})` }), t.join(", "));
      out.append(d);
    });
  } else {
    const got = pick(xs, n);
    got.forEach((x) => out.append(chip(x)));
    out.dataset.value = got.join("|");
  }
  play("success");
});

// ---- dice & coin ---------------------------------------------------------------
const PIPS = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"];
const faces = byId("dc-faces");
const dcOut = byId("dc-out");
const hist: string[] = [];
function record(s: string) {
  hist.unshift(s);
  hist.length = Math.min(hist.length, 10);
  byId("dc-hist").textContent = `Last rolls: ${hist.join(" · ")}`;
}
byId("dc-roll").addEventListener("click", () => {
  const n = Number(byId<HTMLSelectElement>("dc-n").value), s = Number(byId<HTMLSelectElement>("dc-s").value);
  const r = roll(n, s);
  const total = r.reduce((a, b) => a + b, 0);
  faces.replaceChildren(...r.map((v) => {
    const el = document.createElement("span");
    el.className = "rolling";
    el.textContent = s === 6 ? PIPS[v] : String(v);
    if (s === 6) el.style.fontSize = "3rem";
    return el;
  }));
  dcOut.textContent = n > 1 ? `Rolled ${r.join(" + ")} = ${total}` : `Rolled ${total}`;
  dcOut.dataset.total = String(total);
  dcOut.dataset.faces = r.join(",");
  record(n > 1 ? `${r.join("+")}=${total}` : String(total));
  play("press");
});
byId("dc-coin").addEventListener("click", () => {
  const h = randInt(2) === 0 ? "Heads" : "Tails";
  faces.replaceChildren(Object.assign(document.createElement("span"), { className: "rolling", textContent: h === "Heads" ? "H" : "T" }));
  dcOut.textContent = h;
  delete dcOut.dataset.total;
  record(h);
  play("press");
});

wireToggles();
tabs(document.querySelector<HTMLElement>("#rp [role=tablist]")!, (id) => { if (id === "rp-wheel") requestAnimationFrame(draw); });
draw();
