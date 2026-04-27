import type { Pattern } from '../types.js';
import { jsxText, regionLabel } from '../util.js';

const ctaPattern =
  /\b(subscribe|sign up|signup|get started|start now|try (it )?free|join|buy now|download|install|get the app|book a demo)\b/;

const pattern: Pattern = {
  name: 'clickable/cta',
  group: 'clickable',
  score(region) {
    const name = region.name.toLowerCase();
    const hasKeyword = ctaPattern.test(name);
    const hasLargeBounds = (region.bounds?.w ?? 0) > 200 || (region.bounds?.h ?? 0) > 50;

    if (!hasKeyword && !hasLargeBounds) return 0;

    let s = 0;
    if (hasKeyword) s += 60;
    if (hasLargeBounds) s += 30;
    return s;
  },
  render({ componentName, region }) {
    const label = jsxText(regionLabel(region, 'Get started', 30));
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <button className="inline-flex items-center justify-center rounded-lg bg-purple-600 px-6 py-3 text-base font-semibold text-white shadow-md transition hover:bg-purple-700 hover:shadow-lg">`,
      `      {${label}}`,
      `    </button>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
