// Money calculators UI. Every number stays in this tab; nothing is sent anywhere.
import { byId } from "./common";
import { tabs } from "./tabs";
import { emi, sip, gst, pctOf, whatPct, pctChange, inr, num, words } from "./money-math";

const v = (id: string) => {
  const n = Number(byId<HTMLInputElement>(id).value);
  return Number.isFinite(n) ? n : 0;
};
const set = (id: string, text: string) => { byId(id).textContent = text; };
const withWords = (n: number) => (words(n) ? `${inr(n)} (${words(n)})` : inr(n));

function calcEmi() {
  const p = v("emi-p"), r = v("emi-r"), t = v("emi-t");
  const months = byId<HTMLSelectElement>("emi-u").value === "y" ? t * 12 : t;
  if (p <= 0 || months < 1) { ["emi-out", "emi-prin", "emi-int", "emi-total"].forEach((i) => set(i, "—")); return; }
  const e = emi(p, r, months);
  set("emi-out", inr(e.emi));
  set("emi-prin", withWords(p));
  set("emi-int", withWords(e.totalInterest));
  set("emi-total", withWords(e.totalPayment));
  const share = (p / e.totalPayment) * 100;
  byId("emi-donut").style.setProperty("--a", `${share}%`);
  byId("emi-donut").setAttribute("aria-label", `Principal ${Math.round(share)}%, interest ${100 - Math.round(share)}% of the total payment`);
  byId("emi-rows").replaceChildren(...e.schedule.map((row) => {
    const tr = document.createElement("tr");
    for (const c of [String(row.year), inr(row.principal), inr(row.interest), inr(row.balance)]) {
      const td = document.createElement("td");
      td.textContent = c;
      tr.append(td);
    }
    return tr;
  }));
}

function calcSip() {
  const p = v("sip-p"), r = v("sip-r"), y = v("sip-y"), s = v("sip-s");
  if (p <= 0 || y <= 0) { ["sip-out", "sip-inv", "sip-gain"].forEach((i) => set(i, "—")); return; }
  const res = sip(p, r, y, s);
  set("sip-out", withWords(res.value));
  set("sip-inv", withWords(res.invested));
  set("sip-gain", withWords(res.gains));
  const share = (res.invested / res.value) * 100;
  byId("sip-donut").style.setProperty("--a", `${share}%`);
  byId("sip-donut").setAttribute("aria-label", `Invested ${Math.round(share)}%, gains ${100 - Math.round(share)}% of the value`);
}

function calcGst() {
  const g = gst(v("gst-a"), Number(byId<HTMLSelectElement>("gst-r").value),
    byId<HTMLSelectElement>("gst-m").value as "add" | "remove");
  set("gst-net", inr(g.net, 2));
  set("gst-tax", inr(g.gst, 2));
  set("gst-gross", inr(g.gross, 2));
  set("gst-half", inr(g.half, 2));
}

function calcPct() {
  set("p1-out", num(pctOf(v("p1-a"), v("p1-b")), 4));
  const w = whatPct(v("p2-a"), v("p2-b"));
  set("p2-out", Number.isFinite(w) ? `${num(w, 4)}%` : "—");
  const c = pctChange(v("p3-a"), v("p3-b"));
  set("p3-out", Number.isFinite(c) ? `${c > 0 ? "+" : ""}${num(c, 4)}% (${c >= 0 ? "increase" : "decrease"})` : "—");
}

const wire = (panel: string, fn: () => void) => {
  const el = byId(panel);
  el.addEventListener("input", fn);
  el.addEventListener("change", fn);
  fn();
};
wire("mc-emi", calcEmi);
wire("mc-sip", calcSip);
wire("mc-gst", calcGst);
wire("mc-pct", calcPct);
tabs(document.querySelector<HTMLElement>("#mc [role=tablist]")!);

