import type { Pattern } from '../types.js';
import { jsxText, regionTitle } from '../util.js';

const pattern: Pattern = {
  name: 'landmark/footer',
  group: 'landmark',
  score(region) {
    return region.detection === 'sem-footer' ? 100 : 0;
  },
  render({ componentName, region }) {
    const title = jsxText(regionTitle(region, 60));
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <footer className="mt-12 border-t border-slate-200 bg-slate-50 px-6 py-8 text-sm text-slate-600">`,
      `      <div className="mx-auto flex w-full max-w-6xl flex-col gap-2 md:flex-row md:items-center md:justify-between">`,
      `        <span>{${title}}</span>`,
      `        <span className="text-xs text-slate-400">canvas-engine · pattern-library</span>`,
      `      </div>`,
      `    </footer>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
