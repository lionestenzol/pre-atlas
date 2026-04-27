import type { Pattern } from '../types.js';
import { jsxText, leafTag, regionLabel } from '../util.js';

const pattern: Pattern = {
  name: 'clickable/pill',
  group: 'clickable',
  score(region) {
    const name = region.name.trim();
    const nameLength = name.length;
    if (nameLength > 30) return 0;

    // Two signal classes for "pill text":
    //   strong badge · all-caps (BETA, AI) or numeric/symbolic (+5, 99%)
    //                · always counts when compact bounds present
    //   short alpha  · ≤6 chars · counts only with TIGHT pill geometry
    //                · prevents short nav labels (Search, People, About)
    //                · from winning when their bounds are normal nav size
    const isStrongBadgeText =
      /^[A-Z][A-Z0-9]*$/.test(name) ||
      /^[\d+\-*#%]+$/.test(name);
    const isShortAlpha = nameLength <= 6;

    if (!region.bounds) {
      return isStrongBadgeText ? 35 : 15;
    }

    const { w, h } = region.bounds;
    const compact = w >= 30 && w <= 150 && h < 36;
    const tightPillGeometry = w >= 28 && w <= 80 && h <= 28;

    let s: number;
    // Strong pill · earns the perfect-match score that beats link (95) and
    // button (90): badge text + compact bounds, OR short alpha + tight geometry.
    if ((isStrongBadgeText && compact) || (isShortAlpha && tightPillGeometry)) s = 100;
    // Borderline · stay below button/link
    else if (isShortAlpha || isStrongBadgeText) s = 25;
    else if (compact) s = 40;
    else s = 10;

    // Real `<button>` elements (and ARIA button-likes such as
    // `<div role="button">`) should render as button, not pill — cap pill
    // score so compact short-label action buttons (Save, Back, Login) don't
    // outrank clickable/button when leaf or ARIA truth says it's a button.
    // (Note: r9-aria-role is currently a single literal · once the producer
    // distinguishes role=button from role=link/tab, this can be tightened.)
    const isButtonLike =
      leafTag(region.selector) === 'button' ||
      region.detection === 'r9-aria-role';
    if (isButtonLike) s = Math.min(s, 40);
    return s;
  },
  render({ componentName, region }) {
    const label = jsxText(regionLabel(region, 'Tag', 24));
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <button className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100">`,
      `      {${label}}`,
      `    </button>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
