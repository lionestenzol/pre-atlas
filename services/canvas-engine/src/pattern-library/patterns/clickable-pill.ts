import type { Pattern } from '../types.js';
import { jsxText, regionTitle } from '../util.js';

const pattern: Pattern = {
  name: 'clickable/pill',
  group: 'clickable',
  score(region) {
    const nameLength = region.name.length;
    if (nameLength > 30) return 0;

    if (!region.bounds) {
      return nameLength <= 18 ? 35 : 20;
    }

    const { w, h } = region.bounds;
    // perfect match wins over generic clickable/button (90) and clickable/link (95)
    if (nameLength <= 18 && w >= 40 && w <= 150 && h < 40) {
      return 100;
    }

    if (w >= 40 && w <= 150 && h < 40) {
      return 50;
    }

    return nameLength <= 18 ? 25 : 10;
  },
  render({ componentName, region }) {
    const label = jsxText(regionTitle(region, 24));
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
