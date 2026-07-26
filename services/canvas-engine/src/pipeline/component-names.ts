// canvas-engine · shared region→component naming · single source of truth.
//
// The deterministic edit loop resolves component files by
// src/components/<toPascalCase(name)>.jsx, so generation (url-to-clone) and
// resolution (edit-loop) MUST derive component names identically. Both import
// from here so the helper can never drift between copies.

import type { AnatomyV1 } from '../adapter/v1-schema.js';

// Split on whitespace/hyphens, strip non-alphanumerics, capitalize each part,
// then prefix `R` when the result would start with a digit (an invalid JSX
// identifier). Returns '' for input with no alphanumeric content; callers apply
// their own fallback (e.g. `toPascalCase(name) || `Region${n}``).
export function toPascalCase(value: string): string {
  const cleaned = value
    .split(/[\s-]+/)
    .map((part) => part.replace(/[^a-zA-Z0-9]/g, ''))
    .filter((part) => part.length > 0)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1));

  const joined = cleaned.join('');
  return /^[0-9]/.test(joined) ? `R${joined}` : joined;
}

// Map region.id → unique PascalCase component name. Regions are processed in
// ascending `n` order; a repeated base name gets the region's `n` appended so
// every component file stays distinct. This is the contract the edit loop uses
// to resolve src/components/<name>.jsx.
export function buildComponentNameMap(envelope: AnatomyV1): Map<string, string> {
  const seen = new Map<string, number>();
  const result = new Map<string, string>();
  const sorted = [...envelope.regions].sort((l, r) => l.n - r.n);
  for (const region of sorted) {
    const baseName = toPascalCase(region.name) || `Region${region.n}`;
    const idx = seen.get(baseName) ?? 0;
    seen.set(baseName, idx + 1);
    const componentName = idx === 0 ? baseName : `${baseName}${region.n}`;
    result.set(region.id, componentName);
  }
  return result;
}
