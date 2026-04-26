import type { Pattern } from '../types.js';
import { jsxText, regionTitle } from '../util.js';

const pattern: Pattern = {
  name: 'list/grid',
  group: 'list',
  score(region) {
    if (!region.bounds) return 80;
    if (region.bounds.w > 600) return 150;
    return 0;
  },
  render({ componentName, region }) {
    const title = jsxText(regionTitle(region, 60));
    return [
      `export default function ${componentName}() {`,
      `  const items = ['Item 1', 'Item 2', 'Item 3', 'Item 4', 'Item 5', 'Item 6'];`,
      `  return (`,
      `    <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">`,
      `      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{${title}}</h3>`,
      `      <div className="mt-3 grid gap-3 grid-cols-2 md:grid-cols-3">`,
      `        {items.map((item) => (`,
      `          <div key={item} className="rounded-lg bg-white p-3 ring-1 ring-slate-200 text-sm text-slate-700">`,
      `            {item}`,
      `          </div>`,
      `        ))}`,
      `      </div>`,
      `    </section>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
