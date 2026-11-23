// Typing speed test UI. The passage and everything typed stay in this tab.
import { byId } from "./common";
import { score, passage as makePassage } from "./typing-math";
import { play, wireToggles } from "./sfx";

const dur = byId<HTMLSelectElement>("tt-dur");
const kind = byId<HTMLSelectElement>("tt-words");
const ownBox = byId<HTMLDetailsElement>("tt-own");
const ownText = byId<HTMLTextAreaElement>("tt-text");
const view = byId("tt-passage");
const input = byId<HTMLTextAreaElement>("tt-input");
const timeEl = byId("tt-time");
const wpmLive = byId("tt-wpm-live");
const accLive = byId("tt-acc-live");
const bar = byId("tt-bar");
const result = byId("tt-result");
const wpmOut = byId("tt-wpm");
const summary = byId("tt-summary");
const BEST_KEY = "uh-typing-best";

let text = "";
let startedAt = 0;
let timer = 0;
let done = false;

const seconds = () => Number(dur.value);
const ownPassage = () => ownText.value.replace(/\s+/g, " ").trim();

function render() {
  const typed = input.value;
  // Show a window around the caret so long passages scroll with the typist.
  const from = Math.max(0, text.lastIndexOf(" ", Math.max(0, typed.length - 60)) + 1);
  const to = Math.min(text.length, from + 320);
  const frag = document.createDocumentFragment();
  for (let i = from; i < to; i++) {
    const s = document.createElement("span");
    s.textContent = text[i];
    if (i < typed.length) s.className = typed[i] === text[i] ? "ok" : "bad";
    else if (i === typed.length) s.className = "cur";
    frag.append(s);
  }
  view.replaceChildren(frag);
}

function reset(newText = true) {
  clearInterval(timer);
  startedAt = 0;
  done = false;
  if (newText || !text) {
    const own = kind.value === "custom" ? ownPassage() : "";
    text = own || makePassage(kind.value === "punct" ? "punct" : "common", Math.max(60, seconds() * 2.5));
    if (kind.value === "custom" && !own) ownBox.open = true;
  }
  input.value = "";
  input.disabled = false;
  result.hidden = true;
  timeEl.textContent = String(seconds());
  wpmLive.textContent = "0";
  accLive.textContent = "100%";
  bar.style.width = "0";
  render();
}

function tick() {
  if (!startedAt || done) return;
  const elapsed = Math.min(Date.now() - startedAt, seconds() * 1000);
  const left = Math.max(0, seconds() - Math.floor(elapsed / 1000));
  timeEl.textContent = String(left);
  bar.style.width = `${(elapsed / (seconds() * 1000)) * 100}%`;
  const s = score(text, input.value, elapsed);
  wpmLive.textContent = String(s.wpm);
  accLive.textContent = `${s.accuracy}%`;
  if (elapsed >= seconds() * 1000) finish(seconds() * 1000);
}

function best(wpm: number): number {
  try {
    if (localStorage.getItem("uh-consent") === "reject") return wpm;
    const all = JSON.parse(localStorage.getItem(BEST_KEY) || "{}") as Record<string, number>;
    const k = dur.value;
    const prev = all[k] ?? 0;
    if (wpm > prev) { all[k] = wpm; localStorage.setItem(BEST_KEY, JSON.stringify(all)); }
    return Math.max(prev, wpm);
  } catch { return wpm; }
}

function finish(elapsedMs: number) {
  if (done) return;
  done = true;
  clearInterval(timer);
  input.disabled = true;
  const s = score(text, input.value, elapsedMs);
  const secs = Math.round(elapsedMs / 1000);
  const b = best(s.wpm);
  wpmOut.textContent = String(s.wpm);
  wpmLive.textContent = String(s.wpm);
  accLive.textContent = `${s.accuracy}%`;
  timeEl.textContent = String(Math.max(0, seconds() - secs));
  bar.style.width = "100%";
  summary.textContent = `${s.wpm} WPM · ${s.accuracy}% accuracy · ${s.correct} of ${s.typed} characters right · ` +
    `${s.words} words in ${secs} s · raw ${s.rawWpm} WPM` + (b > s.wpm ? ` · your best at this length: ${b} WPM` : "");
  summary.dataset.kind = "ok";
  result.hidden = false;
  play(s.accuracy >= 95 ? "achievement" : "success");
}

input.addEventListener("input", () => {
  if (done) return;
  if (!startedAt && input.value) {
    startedAt = Date.now();
    timer = window.setInterval(tick, 200);
  }
  render();
  // Finished the whole (custom) passage before the time ran out.
  if (input.value.length >= text.length && startedAt) finish(Math.max(Date.now() - startedAt, 1000));
  else tick();
});
// Stop the browser jumping focus to the next field on Tab; a typing test has no use for Tab.
input.addEventListener("keydown", (e) => { if (e.key === "Tab") e.preventDefault(); });
input.addEventListener("paste", (e) => e.preventDefault());

byId("tt-restart").addEventListener("click", () => { reset(false); input.focus(); });
byId("tt-new").addEventListener("click", () => { reset(true); input.focus(); });
dur.addEventListener("change", () => reset(true));
kind.addEventListener("change", () => reset(true));
ownText.addEventListener("input", () => {
  if (ownPassage()) { kind.value = "custom"; ownBox.open = true; reset(true); }
});

wireToggles();
reset(true);
