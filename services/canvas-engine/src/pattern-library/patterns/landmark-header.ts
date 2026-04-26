import type { Pattern } from '../types.js';
import { jsxText, regionTitle } from '../util.js';

const pattern: Pattern = {
  name: 'landmark/header',
  group: 'landmark',
  score(region) {
    return region.detection === 'sem-header' ? 100 : 0;
  },
  render({ componentName, region }) {
    const title = jsxText(regionTitle(region, 60));
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <header className="flex w-full items-center justify-between border-b border-slate-200 bg-white px-6 py-4 shadow-sm">`,
      `      <div className="text-base font-semibold tracking-tight text-slate-900">{${title}}</div>`,
      `      <nav className="flex items-center gap-4 text-sm text-slate-600">`,
      `        <a href="#" className="hover:text-slate-900">Home</a>`,
      `        <a href="#" className="hover:text-slate-900">Docs</a>`,
      `        <a href="#" className="hover:text-slate-900">Pricing</a>`,
      `      </nav>`,
      `    </header>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
