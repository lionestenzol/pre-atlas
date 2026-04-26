// canvas-engine pattern-library · shared JSX-emit helpers

import type { Region } from '../adapter/v1-schema.js';

/** JSON-quote a string for inline use as a JSX text expression. */
export function jsxText(value: string): string {
  return JSON.stringify(value);
}

/** Returns the n badge string e.g. "n7". */
export function nBadge(region: Region): string {
  return `n${region.n}`;
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
  const tint = LAYER_TINTS[region.layer];
  return [
    `      <div className="flex items-center justify-between text-xs uppercase tracking-[0.2em] text-slate-500">`,
    `        <span>${jsxText(region.layer.toUpperCase() + ' · ' + (region.detection ?? ''))}</span>`,
    `        <span className="rounded-full ${tint.replace('50', '100')} px-2 py-0.5 font-medium">${jsxText(nBadge(region))}</span>`,
    `      </div>`,
  ].join('\n');
}

/** Returns first line of region.name (plus indicator if truncated). */
export function regionTitle(region: Region, maxChars = 80): string {
  const raw = (region.name || `Region ${region.n}`).trim();
  if (raw.length <= maxChars) return raw;
  return raw.slice(0, maxChars - 1) + '…';
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
