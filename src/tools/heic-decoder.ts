// Fallback HEIC decoder for browsers without built-in HEIC support (Chrome,
// Edge, Firefox on Windows/Android/Linux).
//
// Uses libheif (with libde265) via libheif-js, which is LGPL-3.0. It is shipped
// UNMODIFIED as its own file, /vendor/libheif/libheif-bundle.mjs (copied by
// scripts/copy-vendor.mjs), loaded only here and only when the native decode
// failed. Users can swap that file for their own build: that, plus the licence
// text and source link below, is how the LGPL terms are met.
// Owner decision on this copyleft exception: see the PR description.

export const FALLBACK_NOTE = 'Browsers without built-in HEIC support use '
  + '<a href="https://github.com/strukturag/libheif" rel="noopener">libheif</a> '
  + '(<a href="/vendor/libheif/LICENSE-libheif-wasm.txt">LGPL-3.0</a>, '
  + '<a href="https://github.com/catdad-experiments/libheif-js/tree/v1.23.5" rel="noopener">source</a>), '
  + 'loaded unmodified from this site. It runs on your device like the rest of the page.';

const LIB_URL = "/vendor/libheif/libheif-bundle.mjs";

interface HeifImage {
  get_width(): number;
  get_height(): number;
  display(img: { data: Uint8ClampedArray; width: number; height: number }, cb: (r: unknown) => void): void;
  free?(): void;
}
interface LibHeif { HeifDecoder: new () => { decode(buf: Uint8Array): HeifImage[] } }

let libP: Promise<LibHeif> | null = null;
function lib(): Promise<LibHeif> {
  return (libP ??= import(/* @vite-ignore */ LIB_URL).then(async (m) => {
    const made = m.default();
    return (typeof made?.then === "function" ? await made : made) as LibHeif;
  }));
}

export async function decodeHeicFallback(file: File): Promise<ImageBitmap> {
  let L: LibHeif;
  try { L = await lib(); }
  catch { libP = null; throw new Error("The HEIC decoder could not load. Check your connection and try again."); }
  const images = new L.HeifDecoder().decode(new Uint8Array(await file.arrayBuffer()));
  if (!images?.length) throw new Error("This file is not a HEIC/HEIF photo, or it is damaged.");
  const img = images[0];
  const width = img.get_width(), height = img.get_height();
  const out = new ImageData(width, height);
  try {
    await new Promise<void>((resolve, reject) => img.display({ data: out.data, width, height },
      (r) => (r ? resolve() : reject(new Error("This HEIC photo could not be decoded.")))));
  } finally {
    images.forEach((i) => i.free?.());
  }
  return createImageBitmap(out);
}
