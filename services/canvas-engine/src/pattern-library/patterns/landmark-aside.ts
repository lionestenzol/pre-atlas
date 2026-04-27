import type { Pattern } from '../types.js';
import { jsxText, regionLabel } from '../util.js';

const pattern: Pattern = {
  name: 'landmark/aside',
  group: 'landmark',
  score(region) {
    return region.detection === 'sem-aside' ? 150 : 0;
  },
  render({ componentName, region }) {
    const title = jsxText(regionLabel(region, 'Sidebar', 60));
    const desc = jsxText(region.desc || 'Sidebar content placeholder.');

    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <aside className="flex flex-col gap-3 rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">`,
      `      <h3 className="text-sm font-semibold text-slate-900">{${title}}</h3>`,
      `      <p className="text-sm text-slate-600">{${desc}}</p>`,
      `      <a href="#" className="text-sm font-medium text-slate-900 hover:text-slate-700">Learn more →</a>`,
      `    </aside>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
