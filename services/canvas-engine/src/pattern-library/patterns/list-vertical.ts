import type { Pattern } from '../types.js';
import { jsxText, regionLabel } from '../util.js';

const pattern: Pattern = {
  name: 'list/vertical',
  group: 'list',
  score: () => 100,
  render({ componentName, region }) {
    const title = jsxText(regionLabel(region, 'Items', 60));
    return [
      `export default function ${componentName}() {`,
      `  const items = [${region.n}, ${region.n + 1}, ${region.n + 2}, ${region.n + 3}];`,
      `  return (`,
      `    <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">`,
      `      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{${title}}</h3>`,
      `      <ul className="mt-3 divide-y divide-slate-200">`,
      `        {items.map((i) => (`,
      `          <li key={i} className="flex items-center justify-between py-2 text-sm text-slate-700">`,
      `            <span>Item {i}</span>`,
      `            <span className="text-xs text-slate-400">→</span>`,
      `          </li>`,
      `        ))}`,
      `      </ul>`,
      `    </section>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
