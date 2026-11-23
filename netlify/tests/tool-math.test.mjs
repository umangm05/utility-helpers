// Known-answer unit tests for the pure maths behind the UH-T3 tools
// (money, dates, typing score, randomness). Node >= 23.6 runs the .ts sources
// directly (type stripping), so these check the exact code the pages ship.
import { test } from "node:test";
import assert from "node:assert/strict";
import { emi, sip, gst, pctOf, whatPct, pctChange, inr, words } from "../../src/tools/money-math.ts";
import { parse, age, ymd, daysBetween, weekdays, split } from "../../src/tools/date-math.ts";
import { score } from "../../src/tools/typing-math.ts";
import { randInt, between, pick, teams, roll, shuffle, entries, MAX_RANGE } from "../../src/tools/random.ts";

test("EMI: ₹10,00,000 at 10% for 20 years = ₹9,650/month (bank reducing-balance formula)", () => {
  const e = emi(1_000_000, 10, 240);
  assert.equal(e.emi.toFixed(2), "9650.22");
  assert.equal(inr(e.emi), "₹9,650");
  assert.equal(inr(e.totalInterest), "₹13,16,052");
  assert.equal(e.schedule.length, 20);
  assert.ok(Math.abs(e.schedule.at(-1).balance) < 1e-6, "loan fully repaid");
  const sumPrincipal = e.schedule.reduce((s, r) => s + r.principal, 0);
  assert.ok(Math.abs(sumPrincipal - 1_000_000) < 1e-3);
  assert.equal(emi(120_000, 0, 12).emi, 10_000, "0% interest = principal / months");
});

test("SIP: ₹5,000/month, 12%, 10 years = ₹11,61,695 (start-of-month convention)", () => {
  const s = sip(5000, 12, 10);
  assert.equal(inr(s.value), "₹11,61,695");
  assert.equal(s.invested, 600_000);
  assert.equal(words(s.value), "11.62 lakh");
  const up = sip(5000, 12, 2, 10);
  assert.equal(up.invested, 5000 * 12 + 5500 * 12, "10% step-up raises the 2nd year's amount");
});

test("GST: add 18% to ₹1,000 = ₹1,180; remove 18% from ₹1,180 = ₹1,000 + ₹180 (₹90 CGST + ₹90 SGST)", () => {
  const a = gst(1000, 18, "add");
  assert.deepEqual([a.net, a.gst, a.gross, a.half], [1000, 180, 1180, 90]);
  const r = gst(1180, 18, "remove");
  assert.equal(r.net.toFixed(2), "1000.00");
  assert.equal(r.gst.toFixed(2), "180.00");
});

test("percentages", () => {
  assert.equal(pctOf(15, 200), 30);
  assert.equal(whatPct(30, 200), 15);
  assert.equal(pctChange(200, 250), 25);
  assert.equal(pctChange(250, 200), -20);
  assert.ok(Number.isNaN(whatPct(1, 0)));
});

test("age: 15 May 1990 on 23 Nov 2026 = 36 y 6 m 8 d, 13,341 days, born on a Tuesday", () => {
  const a = age(parse("1990-05-15"), parse("2026-11-23"));
  assert.deepEqual([a.years, a.months, a.days], [36, 6, 8]);
  assert.equal(a.totalDays, 13_341);
  assert.equal(a.bornOn, "Tuesday");
  assert.equal(a.nextBirthday, "2027-05-15");
  assert.equal(a.daysToBirthday, 173);
  assert.equal(age(parse("2000-01-01"), parse("1999-01-01")), null, "dob after date");
});

test("age: leap-day birthday turns over on 28 Feb in common years", () => {
  const a = age(parse("2000-02-29"), parse("2027-02-28"));
  assert.deepEqual([a.years, a.months, a.days], [27, 0, 0]);
  assert.equal(a.daysToBirthday, 0);
});

test("date difference", () => {
  assert.equal(daysBetween(parse("2026-01-01"), parse("2026-12-31")), 364);
  assert.equal(weekdays(parse("2026-01-01"), parse("2027-01-01")), 261);
  assert.deepEqual(ymd(parse("2026-01-31"), parse("2026-03-01")), { years: 0, months: 1, days: 1 });
  assert.equal(parse("2026-02-30"), null, "impossible date rejected");
  assert.deepEqual(split(90_061_000), { d: 1, h: 1, m: 1, s: 1 });
});

test("typing score: 50 correct characters in 15 s = 40 WPM, 100%; one typo = 39 WPM, 98%", () => {
  const p = "the quick brown fox jumps over the lazy dog again and again until the sun sets";
  const ok = score(p, p.slice(0, 50), 15_000);
  assert.deepEqual([ok.wpm, ok.accuracy, ok.errors], [40, 100, 0]);
  const typo = score(p, "x" + p.slice(1, 50), 15_000);
  assert.deepEqual([typo.wpm, typo.accuracy, typo.errors, typo.rawWpm], [39, 98, 1, 40]);
});

test("randomness: in range, unbiased-ish, picks distinct, teams balanced", () => {
  const counts = new Array(6).fill(0);
  for (let i = 0; i < 60_000; i++) counts[randInt(6)]++;
  for (const c of counts) assert.ok(c > 9_400 && c < 10_600, `d6 face count ${c} far from 10,000`);
  for (let i = 0; i < 1000; i++) { const v = between(-3, 3); assert.ok(v >= -3 && v <= 3 && Number.isInteger(v)); }
  assert.equal(between(7, 7), 7);
  const p = pick(["a", "b", "c", "d"], 3);
  assert.equal(new Set(p).size, 3);
  assert.deepEqual(pick(["a"], 5), ["a"]);
  const t = teams(["a", "b", "c", "d", "e"], 2).map((x) => x.length).sort();
  assert.deepEqual(t, [2, 3]);
  const r = roll(3, 6);
  assert.equal(r.length, 3);
  assert.ok(r.every((v) => v >= 1 && v <= 6));
  assert.deepEqual(shuffle([1, 2, 3, 4]).sort(), [1, 2, 3, 4]);
  assert.deepEqual(entries(" Asha \n\n Rahul\r\n"), ["Asha", "Rahul"]);
});

test("randomness: huge ranges terminate (regression: n > 2^32 froze the tab)", () => {
  for (const n of [1e10, 2 ** 32 + 1, 2 ** 32, 2 ** 53, 3 * 2 ** 40 + 7]) {
    for (let i = 0; i < 2000; i++) {
      const v = randInt(n);
      assert.ok(Number.isInteger(v) && v >= 0 && v < n, `randInt(${n}) -> ${v}`);
    }
  }
  for (let i = 0; i < 2000; i++) { const v = between(1, 1e10); assert.ok(v >= 1 && v <= 1e10 && Number.isInteger(v)); }
  // 53-bit path is not stuck in the low half: with n = 2^33 roughly half the draws are >= 2^32.
  let high = 0;
  for (let i = 0; i < 4000; i++) if (randInt(2 ** 33) >= 2 ** 32) high++;
  assert.ok(high > 1700 && high < 2300, `high-half count ${high}`);
  assert.equal(MAX_RANGE, 2 ** 53);
  assert.throws(() => randInt(2 ** 53 + 2), RangeError);
  assert.throws(() => randInt(0), RangeError);
  assert.throws(() => between(-(2 ** 53), 2 ** 53), RangeError);
});
