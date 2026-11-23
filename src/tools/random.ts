// Randomness for the picker, wheel, dice and typing passages: the browser's
// CSPRNG (crypto.getRandomValues) with rejection sampling, so every outcome
// is exactly equally likely (no modulo bias). Pure; unit-tested in Node.

/** Largest range randInt supports: every integer below 2^53 is exact in a double. */
export const MAX_RANGE = 2 ** 53;

/**
 * Unbiased random integer in [0, n), for 1 <= n <= 2^53.
 * n <= 2^32 draws one Uint32; larger n draws 53 bits (21 + 32) from two Uint32s.
 * Rejection limit is `space - space % n` (fmod is exact in IEEE doubles), so it
 * is always >= n and the loop terminates with probability >= 1/2 per draw.
 */
export function randInt(n: number): number {
  if (!Number.isInteger(n) || n < 1 || n > MAX_RANGE) throw new RangeError(`randInt(${n})`);
  const c = (globalThis as { crypto?: Crypto }).crypto;
  if (!c?.getRandomValues) return Math.floor(Math.random() * n);
  if (n <= 0x100000000) {
    const lim = 0x100000000 - (0x100000000 % n);
    const a = new Uint32Array(1);
    do c.getRandomValues(a); while (a[0] >= lim);
    return a[0] % n;
  }
  const lim = MAX_RANGE - (MAX_RANGE % n);
  const a = new Uint32Array(2);
  let x: number;
  do {
    c.getRandomValues(a);
    x = (a[0] & 0x1fffff) * 0x100000000 + a[1];
  } while (x >= lim);
  return x % n;
}

/** Random integer in [min, max] inclusive. Throws RangeError if the span exceeds MAX_RANGE. */
export function between(min: number, max: number): number {
  if (!Number.isSafeInteger(min) || !Number.isSafeInteger(max) || max < min) throw new RangeError(`between(${min}, ${max})`);
  return min + randInt(max - min + 1);
}

/** Fisher-Yates shuffle (returns a new array). */
export function shuffle<T>(xs: readonly T[]): T[] {
  const a = xs.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = randInt(i + 1);
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/** `k` distinct items (k clamped to the list length). */
export const pick = <T>(xs: readonly T[], k: number) => shuffle(xs).slice(0, Math.max(0, Math.min(k, xs.length)));

/** Deal `xs` (shuffled) round-robin into `n` teams: sizes differ by at most one. */
export function teams<T>(xs: readonly T[], n: number): T[][] {
  const k = Math.max(1, Math.min(n, xs.length || 1));
  const out: T[][] = Array.from({ length: k }, () => []);
  shuffle(xs).forEach((x, i) => out[i % k].push(x));
  return out;
}

/** Roll `count` dice with `sides` faces. */
export const roll = (count: number, sides: number) => Array.from({ length: count }, () => between(1, sides));

/** Non-empty trimmed lines, max 500 entries of 100 chars. */
export const entries = (text: string) =>
  text.split(/\r?\n/).map((s) => s.trim().slice(0, 100)).filter(Boolean).slice(0, 500);
