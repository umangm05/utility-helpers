// Tool UIs that are real components (src/tools/*.astro) rather than body_html.
// site.config.json names one with `"island": "<key>"`. Each component's script
// (and any library it lazy-imports) is emitted only on the page that renders it.
import ResizeImage from "./ResizeImage.astro";
import PdfTools from "./PdfTools.astro";
import HeicToJpg from "./HeicToJpg.astro";
import QrCode from "./QrCode.astro";
import PassportPhoto from "./PassportPhoto.astro";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const islands: Record<string, any> = {
  "resize-image": ResizeImage,
  "pdf-tools": PdfTools,
  "heic-to-jpg": HeicToJpg,
  "qr-code": QrCode,
  "passport-photo": PassportPhoto,
};
