// canvas-engine pattern-library · shared JSX-emit helpers

import type { Region } from '../adapter/v1-schema.js';

/** JSON-quote a string for inline use as a JSX text expression. */
export function jsxText(value: string): string {
  return JSON.stringify(value);
}

const SIMPLE_SELECTOR_TAG_RE = /^([a-zA-Z][a-zA-Z0-9-]*)/;

/**
 * Extract the DOM tag at the END of a CSS selector path · returns lowercase tag
 * or null if the trailing simple selector doesn't begin with a tag name.
 * Used as independent ground truth — the browser writes the selector, the
 * producer cascade can't lie about the leaf.
 *
 * Handles all combinators (>, +, ~, descendant whitespace) and bare/single-
 * segment selectors (`a`, `a.cta`, `header.site-header`, `header`).
 *
 * Examples:
 *   "a"                    → "a"
 *   "a.cta"                → "a"
 *   "header.site-header"   → "header"
 *   "td > a"               → "a"
 *   "td > a > span"        → "span"
 *   "td > a:nth-of-type(2)" → "a"
 *   ".foo > .bar"          → null   (last segment has no tag)
 *   "[type=button]"        → null
 */
export function leafTag(selector: string | undefined): string | null {
  if (!selector) return null;
  // Split on combinators · `>`, `+`, `~`, or runs of whitespace
  const segments = selector.trim().split(/\s*[>+~]\s*|\s+/);
  const last = segments[segments.length - 1] || '';
  const m = SIMPLE_SELECTOR_TAG_RE.exec(last);
  return m ? m[1].toLowerCase() : null;
}

/**
 * True when the leaf tag of the selector path is `<a>`. Strictly leaf-only —
 * does NOT match ancestor anchors like `... > a > span`. Used by clickable/link
 * to overcome the detection cascade's lossy flattening of `<a>` and `<button>`
 * into the single `r7-native-interactive` literal.
 */
export function isAnchorSelector(selector: string | undefined): boolean {
  return leafTag(selector) === 'a';
}

/** Returns the n badge string e.g. "n7". */
export function nBadge(region: Region): string {
  return `n${region.n}`;
}

/**
 * True when the region name is anatomy's auto-generated placeholder
 * (e.g. "header · 1", "section · 2", "main · main", just "section", "header",
 * "main", "nav", "aside", "footer"). These names leak debug-looking text into
 * the rendered clone, so patterns should swap to a generic label instead.
 */
export function isPlaceholderName(name: string): boolean {
  if (!name) return true;
  const trimmed = name.trim().toLowerCase();
  if (/^(header|footer|nav|main|aside|section)$/.test(trimmed)) return true;
  if (/^(header|footer|nav|main|aside|section)\s*·\s*\S+$/i.test(name.trim())) return true;
  if (/^region\s+\d+$/i.test(trimmed)) return true;
  return false;
}

/** Map of layer → soft Tailwind tint class · matches the deterministic stub vocab. */
export const LAYER_TINTS: Record<Region['layer'], string> = {
  ui: 'bg-purple-50',
  api: 'bg-amber-50',
  ext: 'bg-sky-50',
  lib: 'bg-emerald-50',
  state: 'bg-rose-50',
};

/** Render the "n badge" + region name header used by most patterns. */
export function renderBadgeHeader(region: Region): string {
  return `      <span className="text-xs uppercase tracking-[0.2em] text-slate-500">{${jsxText(nBadge(region))}}</span>`;
}

/** Returns first line of region.name (plus indicator if truncated). */
export function regionTitle(region: Region, maxChars = 80): string {
  const raw = (region.name || `Region ${region.n}`).trim();
  if (raw.length <= maxChars) return raw;
  return raw.slice(0, maxChars - 1) + '…';
}

/**
 * Returns regionTitle(region, max), but when the region's name is a placeholder
 * substitutes the supplied fallback text. Use this in pattern renderers
 * whenever the visible label should be content-like, not debug-like.
 */
export function regionLabel(region: Region, fallback: string, max = 80): string {
  const raw = (region.name || '').trim();
  if (isPlaceholderName(raw)) return fallback;
  return regionTitle(region, max);
}

/** Common section wrapper · returns opening tag + classes. */
export function sectionWrapper(region: Region, extraClasses = ''): string {
  const tint = LAYER_TINTS[region.layer];
  const classes = [
    tint,
    'w-full rounded-2xl border border-slate-200 p-5 shadow-sm',
    extraClasses,
  ].filter(Boolean).join(' ');
  const minH = region.bounds?.h ? ` style={{ minHeight: '${Math.max(region.bounds.h, 96)}px' }}` : '';
  return `    <section className="${classes}"${minH}>`;
}
