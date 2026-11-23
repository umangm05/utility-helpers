// Age / date difference / countdown UI. Dates never leave this tab. The
// countdown "link" keeps its data in the URL #fragment, which browsers never
// send to the server.
import { byId } from "./common";
import { tabs } from "./tabs";
import { parse, iso, age, ymd, daysBetween, weekdays, addDays, split, plural, WEEKDAYS } from "./date-math";
import { play, wireToggles } from "./sfx";

const val = (id: string) => byId<HTMLInputElement>(id).value;
const set = (id: string, t: string) => { byId(id).textContent = t; };
const localToday = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const pretty = (t: number) => {
  const d = new Date(t);
  return `${WEEKDAYS[d.getUTCDay()]}, ${d.getUTCDate()} ${d.toLocaleString("en-IN", { month: "long", timeZone: "UTC" })} ${d.getUTCFullYear()}`;
};
const ymdText = (y: number, m: number, d: number) => `${plural(y, "year")}, ${plural(m, "month")}, ${plural(d, "day")}`;

// ---- age -------------------------------------------------------------------
function calcAge() {
  const dob = parse(val("age-dob")), on = parse(val("age-on"));
  const a = dob !== null && on !== null ? age(dob, on) : null;
  if (!a) {
    set("age-out", dob !== null && on !== null ? "The date of birth is after the 'age on' date." : "Pick a date of birth.");
    ["age-months", "age-weeks", "age-days", "age-wd", "age-next"].forEach((i) => set(i, "—"));
    return;
  }
  set("age-out", ymdText(a.years, a.months, a.days));
  set("age-months", a.totalMonths.toLocaleString("en-IN"));
  set("age-weeks", a.totalWeeks.toLocaleString("en-IN"));
  set("age-days", a.totalDays.toLocaleString("en-IN"));
  set("age-wd", a.bornOn);
  set("age-next", a.daysToBirthday === 0 ? `Today! Turning ${a.turning} 🎉`
    : `in ${plural(a.daysToBirthday, "day")} (turning ${a.turning})`);
}

// ---- difference ------------------------------------------------------------
function calcDiff() {
  const a = parse(val("diff-a")), b0 = parse(val("diff-b"));
  if (a === null || b0 === null) { set("diff-out", "Pick two dates."); return; }
  const incl = byId<HTMLInputElement>("diff-incl").checked;
  const [lo, hi] = a <= b0 ? [a, b0] : [b0, a];
  const hiX = incl ? addDays(hi, 1) : hi;
  const n = daysBetween(lo, hiX);
  set("diff-out", `${plural(n, "day")}${a > b0 ? " (end is before start)" : ""}`);
  const d = ymd(lo, hiX);
  set("diff-ymd", ymdText(d.years, d.months, d.days));
  set("diff-weeks", `${plural(Math.floor(n / 7), "week")}${n % 7 ? `, ${plural(n % 7, "day")}` : ""}`);
  set("diff-wd", weekdays(lo, hiX).toLocaleString("en-IN"));
  calcAdd();
}
function calcAdd() {
  const a = parse(val("diff-a"));
  const n = Math.round(Number(val("add-n")));
  if (a === null || !Number.isFinite(n)) { set("add-out", ""); return; }
  set("add-out", `${iso(a)} ${n >= 0 ? "+" : "−"} ${plural(Math.abs(n), "day")} = ${pretty(addDays(a, n))}`);
}

// ---- countdown -------------------------------------------------------------
let cdTimer = 0;
let rang = false;
function target(): number | null {
  const d = val("cd-date");
  if (!parse(d)) return null;
  const t = new Date(`${d}T${val("cd-time") || "00:00"}`).getTime();   // local time
  return Number.isFinite(t) ? t : null;
}
function paintCd() {
  const t = target();
  const name = val("cd-name").trim();
  if (t === null) { set("cd-out", "Pick a date to count down to."); return; }
  const left = t - Date.now();
  const s = split(left);
  set("cd-d", s.d.toLocaleString("en-IN"));
  set("cd-h", String(s.h).padStart(2, "0"));
  set("cd-m", String(s.m).padStart(2, "0"));
  set("cd-s", String(s.s).padStart(2, "0"));
  const what = name || "the date";
  if (left <= 0) {
    set("cd-out", `${what} has arrived.`);
    if (!rang && left > -2000) { rang = true; play("achievement"); }
  } else {
    set("cd-out", `${plural(s.d, "day")}, ${plural(s.h, "hour")} and ${plural(s.m, "minute")} until ${what}.`);
    rang = false;
  }
}
function startCd() {
  clearInterval(cdTimer);
  paintCd();
  cdTimer = window.setInterval(paintCd, 1000);
}
function fromFragment() {
  const p = new URLSearchParams(location.hash.slice(1));
  const to = p.get("to");
  if (!to) return false;
  const [d, tm] = to.split("T");
  if (!parse(d)) return false;
  byId<HTMLInputElement>("cd-date").value = d;
  if (tm && /^\d{2}:\d{2}$/.test(tm)) byId<HTMLInputElement>("cd-time").value = tm;
  byId<HTMLInputElement>("cd-name").value = (p.get("name") || "").slice(0, 60);
  return true;
}

// ---- wiring ----------------------------------------------------------------
const today = localToday();
byId<HTMLInputElement>("age-on").value = today;
byId<HTMLInputElement>("diff-a").value = today;
const yr = Number(today.slice(0, 4));
byId<HTMLInputElement>("diff-b").value = `${yr}-12-31`;
byId<HTMLInputElement>("cd-date").value = `${yr + 1}-01-01`;

for (const [panel, fn] of [["dt-age", calcAge], ["dt-diff", calcDiff], ["dt-cd", startCd]] as const) {
  byId(panel).addEventListener("input", fn);
  byId(panel).addEventListener("change", fn);
}
byId("add-n").addEventListener("input", calcAdd);
byId("cd-ny").addEventListener("click", () => {
  byId<HTMLInputElement>("cd-date").value = `${new Date().getFullYear() + 1}-01-01`;
  byId<HTMLInputElement>("cd-time").value = "00:00";
  byId<HTMLInputElement>("cd-name").value = "New Year";
  startCd();
});
byId("cd-link").addEventListener("click", async () => {
  const p = new URLSearchParams({ to: `${val("cd-date")}T${val("cd-time") || "00:00"}` });
  if (val("cd-name").trim()) p.set("name", val("cd-name").trim());
  const url = `${location.origin}${location.pathname}#countdown&${p}`;
  try { await navigator.clipboard.writeText(url); set("cd-out", "Link copied. It opens this countdown on any device."); }
  catch { set("cd-out", url); }
});

const select = tabs(document.querySelector<HTMLElement>("#dt [role=tablist]")!, (id) => { if (id === "dt-cd") startCd(); });
// #countdown&to=2027-01-01T00:00&name=... (fragment only)
if (location.hash.startsWith("#countdown&") && fromFragment()) select(2);
wireToggles();
calcAge();
calcDiff();
startCd();
