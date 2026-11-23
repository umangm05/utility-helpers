// Pure scoring/math for the typing test (no DOM). Kept separate so
// netlify/tests/tool-math.test.mjs can check the known answers in Node.
import { randInt } from "./random.ts";

export interface Score {
  typed: number;        // characters typed (compared against the passage)
  correct: number;      // characters that match the passage at the same position
  errors: number;       // typed - correct
  accuracy: number;     // 0..100, rounded
  wpm: number;          // net speed: correct characters / 5 per minute, rounded
  rawWpm: number;       // all typed characters / 5 per minute, rounded
  words: number;        // whole passage words typed with no mistake
}

/** Score `typed` against `passage` after `elapsedMs` (clamped to >= 1 s so an instant paste is finite). */
export function score(passage: string, typed: string, elapsedMs: number): Score {
  const n = Math.min(typed.length, passage.length);
  let correct = 0;
  for (let i = 0; i < n; i++) if (typed[i] === passage[i]) correct++;
  const t = typed.length;
  const minutes = Math.max(elapsedMs, 1000) / 60000;
  // A word counts once the user has typed past it (or reached the end) with every letter right.
  let words = 0;
  const re = /\S+/g;
  for (let m = re.exec(passage); m; m = re.exec(passage)) {
    const end = m.index + m[0].length;
    if (t < end) break;
    if (typed.slice(m.index, end) === m[0]) words++;
  }
  return {
    typed: t,
    correct,
    errors: t - correct,
    accuracy: t ? Math.round((correct / t) * 100) : 100,
    wpm: Math.round(correct / 5 / minutes),
    rawWpm: Math.round(t / 5 / minutes),
    words,
  };
}

export const COMMON = (
  "the of and to in is you that it he was for on are as with his they at be this have from or one had by word " +
  "but not what all were we when your can said there use an each which she do how their if will up other about " +
  "out many then them these so some her would make like him into time has look two more write go see number no " +
  "way could people my than first water been call who oil its now find long down day did get come made may part " +
  "over new sound take only little work know place year live me back give most very after thing our just name " +
  "good sentence man think say great where help through much before line right too mean old any same tell boy " +
  "follow came want show also around form three small set put end does another well large must big even such " +
  "because turn here why ask went men read need land different home us move try kind hand picture again change " +
  "off play spell air away animal house point page letter mother answer found study still learn should world"
).split(" ");

const SENTENCES = [
  "Practice a little every day and your speed will grow.",
  "The train to Mumbai leaves at seven, so pack tonight.",
  "Good typing is mostly rhythm, not raw speed.",
  "Keep your eyes on the text, not on the keyboard.",
  "She paid the bill online and saved the receipt.",
  "Small habits, repeated often, beat big plans.",
  "Can you send the report before Friday's meeting?",
  "We walked along the beach until the sun went down.",
  "Rain or shine, the market opens at nine.",
  "Read the question twice, then write your answer.",
];

export function passage(kind: "common" | "punct", words = 60): string {
  if (kind === "punct") {
    const out: string[] = [];
    let total = 0;
    while (total < words) {
      const s = SENTENCES[randInt(SENTENCES.length)];
      if (out[out.length - 1] === s) continue;
      out.push(s);
      total += s.split(" ").length;
    }
    return out.join(" ");
  }
  return Array.from({ length: words }, () => COMMON[randInt(COMMON.length)]).join(" ");
}
