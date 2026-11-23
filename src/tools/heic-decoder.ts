// Fallback HEIC decoder for browsers without built-in HEIC support.
//
// Every HEIF/HEVC decoder we could find is LGPL (libheif, libde265, ffmpeg),
// and the project's licence rule rejects copyleft by default, so this build
// ships NO fallback: Safari / iOS decode natively; elsewhere we explain.
// (An owner-approved fallback replaces this file; see the PR description.)

export const FALLBACK_NOTE = "";

export async function decodeHeicFallback(_file: File): Promise<ImageBitmap> {
  throw new Error("This browser cannot open HEIC photos. Open the page in Safari on an iPhone, iPad or Mac, "
    + "or set the iPhone camera to Most Compatible to get JPG photos.");
}
