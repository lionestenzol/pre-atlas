import type { Pattern } from '../types.js';
import { jsxText, regionLabel } from '../util.js';

const pattern: Pattern = {
  name: 'landmark/section',
  group: 'landmark',
  score(region) {
    const det = region.detection || '';
    if (det === 'sem-section' || det === 'sem-main' || det === 'sem-aside' || det === 'sem-nav') return 90;
    return 30; // fallback for any landmark we don't have a dedicated pattern for
  },
  render({ componentName, region }) {
    const fallback = region.detection === 'sem-nav'
      ? 'Menu'
      : region.detection === 'sem-aside'
        ? 'Sidebar'
        : 'Section';
    const title = jsxText(regionLabel(region, fallback, 60));
    const desc = region.desc ? `      <p className="mt-2 text-sm text-slate-600">{${jsxText(region.desc)}}</p>` : '';
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">`,
      `      <h2 className="text-lg font-semibold tracking-tight text-slate-900">{${title}}</h2>`,
      desc,
      `    </section>`,
      `  );`,
      `}`,
    ].filter(Boolean).join('\n');
  },
};

export default pattern;
