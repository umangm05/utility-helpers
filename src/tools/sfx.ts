// Subtle UI sounds for the interactive tools (typing test, spin wheel, dice,
// background remover). Audio files: uisfx 0.4.0 "minimal" pack, CC0-1.0
// (public/sfx/LICENSE-AUDIO.txt), self-hosted so they work offline.
//
// - Nothing plays until the user has interacted (sounds are only triggered
//   from user actions), and the AudioContext is created lazily on first use.
// - A `.sfx-toggle` button on the page mutes/unmutes; the choice is kept in
//   localStorage ("uh-sound" = "off"), like the theme choice.
// - Only same-origin GETs of /sfx/*.mp3. No network request carries user input.

export type Cue = "press" | "success" | "error" | "achievement";

const KEY = "uh-sound";
const VOLUME = 0.35;
let ctx: AudioContext | null = null;
const buffers = new Map<Cue, Promise<AudioBuffer | null>>();

function enabled(): boolean {
  try { return localStorage.getItem(KEY) !== "off"; } catch { return true; }
}

function audio(): AudioContext | null {
  if (ctx) return ctx;
  const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AC) return null;
  ctx = new AC();
  return ctx;
}

function load(cue: Cue): Promise<AudioBuffer | null> {
  let p = buffers.get(cue);
  if (!p) {
    p = fetch(`/sfx/${cue}.mp3`)
      .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(String(r.status)))))
      .then((buf) => new Promise<AudioBuffer>((res, rej) => audio()!.decodeAudioData(buf, res, rej)))
      .catch(() => null);
    buffers.set(cue, p);
  }
  return p;
}

/** Play a cue (fire-and-forget). `rate` > 1 makes it shorter/higher, e.g. wheel ticks. */
export function play(cue: Cue, rate = 1): void {
  if (!enabled()) return;
  const ac = audio();
  if (!ac) return;
  if (ac.state === "suspended") ac.resume().catch(() => {});
  load(cue).then((b) => {
    if (!b || !enabled()) return;
    const src = ac.createBufferSource();
    src.buffer = b;
    src.playbackRate.value = rate;
    const g = ac.createGain();
    g.gain.value = VOLUME;
    src.connect(g).connect(ac.destination);
    src.start();
  });
}

/** Wire every `.sfx-toggle` button on the page (aria-pressed = sound on). */
export function wireToggles(): void {
  document.querySelectorAll<HTMLButtonElement>(".sfx-toggle").forEach((btn) => {
    const paint = () => {
      const on = enabled();
      btn.setAttribute("aria-pressed", String(on));
      btn.textContent = on ? "Sound: on" : "Sound: off";
    };
    paint();
    btn.addEventListener("click", () => {
      try { localStorage.setItem(KEY, enabled() ? "off" : "on"); } catch { /* private mode */ }
      paint();
      if (enabled()) play("press");
    });
  });
}
