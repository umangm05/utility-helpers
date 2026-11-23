// Calendar maths for the age / date tools. Pure functions on "YYYY-MM-DD"
// strings, computed in UTC so daylight-saving changes never shift a day.
// Unit-tested in Node (netlify/tests/tool-math.test.mjs).

const DAY = 86_400_000;
export const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export function parse(s: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return null;
  const t = Date.UTC(+m[1], +m[2] - 1, +m[3]);
  const d = new Date(t);
  return d.getUTCMonth() === +m[2] - 1 ? t : null;   // rejects 2026-02-30
}

export const iso = (t: number) => new Date(t).toISOString().slice(0, 10);
const daysIn = (y: number, m0: number) => new Date(Date.UTC(y, m0 + 1, 0)).getUTCDate();

export interface Ymd { years: number; months: number; days: number }

/** a + n calendar months, clamping the day (Jan 31 + 1 month = Feb 28/29). */
function addMonths(a: number, n: number): number {
  const A = new Date(a);
  const y = A.getUTCFullYear() + Math.floor((A.getUTCMonth() + n) / 12);
  const m = (((A.getUTCMonth() + n) % 12) + 12) % 12;
  return Date.UTC(y, m, Math.min(A.getUTCDate(), daysIn(y, m)));
}

export const daysBetween = (a: number, b: number) => Math.round((b - a) / DAY);

/**
 * Calendar difference a -> b (a <= b): the most whole months that fit
 * (day clamped at month end), then the remaining days. Jan 31 -> Mar 1 = 1 month 1 day.
 */
export function ymd(a: number, b: number): Ymd {
  const A = new Date(a), B = new Date(b);
  let total = (B.getUTCFullYear() - A.getUTCFullYear()) * 12 + (B.getUTCMonth() - A.getUTCMonth());
  let at = addMonths(a, total);
  while (total > 0 && at > b) at = addMonths(a, --total);
  return { years: Math.floor(total / 12), months: total % 12, days: daysBetween(at, b) };
}

/** Monday-Friday days in [a, b) (b exclusive), O(1). */
export function weekdays(a: number, b: number): number {
  const n = daysBetween(a, b);
  if (n <= 0) return 0;
  const full = Math.floor(n / 7);
  let count = full * 5;
  const start = new Date(a).getUTCDay();
  for (let i = 0; i < n % 7; i++) {
    const wd = (start + i) % 7;
    if (wd !== 0 && wd !== 6) count++;
  }
  return count;
}

export interface Age extends Ymd {
  totalDays: number;
  totalWeeks: number;
  totalMonths: number;
  bornOn: string;            // weekday name
  nextBirthday: string;      // YYYY-MM-DD
  daysToBirthday: number;    // 0 = today
  turning: number;
}

/** Age on `on` for someone born on `dob`. Feb 29 birthdays fall on Feb 28 in common years. */
export function age(dob: number, on: number): Age | null {
  if (on < dob) return null;
  const d = ymd(dob, on);
  const D = new Date(dob), O = new Date(on);
  const bdayIn = (y: number) => {
    const m = D.getUTCMonth();
    return Date.UTC(y, m, Math.min(D.getUTCDate(), daysIn(y, m)));
  };
  let next = bdayIn(O.getUTCFullYear());
  if (next < on) next = bdayIn(O.getUTCFullYear() + 1);
  const totalDays = daysBetween(dob, on);
  return {
    ...d,
    totalDays,
    totalWeeks: Math.floor(totalDays / 7),
    totalMonths: d.years * 12 + d.months,
    bornOn: WEEKDAYS[D.getUTCDay()],
    nextBirthday: iso(next),
    daysToBirthday: daysBetween(on, next),
    turning: new Date(next).getUTCFullYear() - D.getUTCFullYear(),
  };
}

export const addDays = (t: number, n: number) => t + n * DAY;

/** Split a millisecond span into d/h/m/s for the countdown. */
export function split(ms: number): { d: number; h: number; m: number; s: number } {
  const t = Math.max(0, Math.floor(ms / 1000));
  return { d: Math.floor(t / 86400), h: Math.floor((t % 86400) / 3600), m: Math.floor((t % 3600) / 60), s: t % 60 };
}

export const plural = (n: number, w: string) => `${n.toLocaleString("en-IN")} ${w}${n === 1 ? "" : "s"}`;
