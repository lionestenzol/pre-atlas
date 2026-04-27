import type { Pattern } from '../types.js';
import { jsxText, regionLabel } from '../util.js';

const pattern: Pattern = {
  name: 'clickable/icon-button',
  group: 'clickable',
  score(region) {
    let s = 30;
    const det = region.detection || '';
    if (det === 'r11-icon-sized-interactive') s += 50;
    if (region.bounds && region.bounds.w < 48 && region.bounds.h < 48) s += 15;
    return s;
  },
  render({ componentName, region }) {
    const label = jsxText(regionLabel(region, 'Open', 24));
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <button aria-label={${label}} className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:bg-slate-50">`,
      `      <span className="text-base">⚙</span>`,
      `    </button>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
