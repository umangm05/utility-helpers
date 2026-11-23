// Money maths (EMI, SIP, GST, percentage). Pure functions, no DOM, so the
// known answers are unit-tested in Node (netlify/tests/tool-math.test.mjs).

export interface EmiRow { year: number; principal: number; interest: number; balance: number }
export interface Emi { emi: number; months: number; totalInterest: number; totalPayment: number; schedule: EmiRow[] }

/** Reducing-balance loan EMI. `annualRate` in percent, `months` >= 1. */
export function emi(principal: number, annualRate: number, months: number): Emi {
  const n = Math.max(1, Math.round(months));
  const i = annualRate / 12 / 100;
  const pay = i === 0 ? principal / n : (principal * i * (1 + i) ** n) / ((1 + i) ** n - 1);
  const schedule: EmiRow[] = [];
  let bal = principal, yp = 0, yi = 0;
  for (let m = 1; m <= n; m++) {
    const int = bal * i;
    const prin = Math.min(pay - int, bal);
    bal = Math.max(0, bal - prin);
    yp += prin; yi += int;
    if (m % 12 === 0 || m === n) {
      schedule.push({ year: Math.ceil(m / 12), principal: yp, interest: yi, balance: bal });
      yp = 0; yi = 0;
    }
  }
  return { emi: pay, months: n, totalPayment: pay * n, totalInterest: pay * n - principal, schedule };
}

export interface Sip { invested: number; value: number; gains: number }

/**
 * Monthly SIP future value, contributions at the START of each month (the
 * convention used by Indian AMC/broker calculators): FV = P·((1+i)^n − 1)/i·(1+i).
 * `stepUp` (percent) raises the monthly amount once a year.
 */
export function sip(monthly: number, annualReturn: number, years: number, stepUp = 0): Sip {
  const i = annualReturn / 12 / 100;
  const n = Math.max(1, Math.round(years * 12));
  let value = 0, invested = 0, p = monthly;
  for (let m = 0; m < n; m++) {
    if (m > 0 && m % 12 === 0) p *= 1 + stepUp / 100;
    invested += p;
    value = (value + p) * (1 + i);
  }
  return { invested, value, gains: value - invested };
}

export interface Gst { net: number; gst: number; gross: number; half: number }

/** mode "add": amount is before tax. mode "remove": amount already includes GST. */
export function gst(amount: number, ratePct: number, mode: "add" | "remove"): Gst {
  const r = ratePct / 100;
  const net = mode === "add" ? amount : amount / (1 + r);
  const tax = net * r;
  return { net, gst: tax, gross: net + tax, half: tax / 2 };
}

export const pctOf = (pct: number, of: number) => (pct / 100) * of;
export const whatPct = (part: number, whole: number) => (whole === 0 ? NaN : (part / whole) * 100);
export const pctChange = (from: number, to: number) => (from === 0 ? NaN : ((to - from) / Math.abs(from)) * 100);

/** ₹ with Indian digit grouping (12,34,567.89). */
export function inr(n: number, dp = 0): string {
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: dp,
    maximumFractionDigits: dp }).format(n);
}

/** Plain number, Indian grouping, up to `dp` decimals (trailing zeros dropped). */
export function num(n: number, dp = 2): string {
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: dp }).format(n);
}

/** Lakh/crore words for big rupee amounts: 1161695 -> "11.62 lakh". */
export function words(n: number): string {
  const a = Math.abs(n);
  if (a >= 1e7) return `${num(n / 1e7, 2)} crore`;
  if (a >= 1e5) return `${num(n / 1e5, 2)} lakh`;
  return "";
}
