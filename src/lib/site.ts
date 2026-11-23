// site.config.json is the single source of truth. Everything here is a typed
// view over it plus the small helpers the pages share.
import raw from "../../site.config.json";

export interface Faq { q: string; a: string }
export interface Tool {
  slug: string;
  name: string;
  section: string;
  icon: string;
  preview: string;
  /** Content kinds the home "drop anything" zone can hand to this tool. */
  accepts: string[];
  summary: string;
  title: string;
  description: string;
  intro?: string;
  faq?: Faq[];
  body_html?: string;
  /** Name of a component in src/tools/ that renders this tool instead of body_html. */
  island?: string;
}
export interface Section { id: string; name: string; blurb: string }
export interface Site {
  name: string;
  baseUrl: string;
  tagline: string;
  description: string;
  author: string;
  github: string;
  locale: string;
  themeColor: string;
  adsenseClient?: string;
}
export interface Sibling { name: string; url: string; blurb: string }

export const site = raw.site as Site;
export const tools = raw.tools as Tool[];
export const sections = raw.sections as Section[];
export const moreFromUs = raw.moreFromUs as Sibling[];

// SEO field budgets (Google truncates around these widths).
export const TITLE_MAX = 60;
export const DESC_MAX = 155;

export const pageUrl = (path: string) => site.baseUrl.replace(/\/$/, "") + path;

export const homeTitle = `${site.name} — ${site.tagline}`.slice(0, TITLE_MAX);

/** Compact list shipped to the client for the Ctrl+K bar, recents and drop zone. */
export const clientTools = tools.map((t) => ({
  slug: t.slug,
  name: t.name,
  icon: t.icon,
  section: sections.find((s) => s.id === t.section)?.name ?? "",
  accepts: t.accepts,
}));
