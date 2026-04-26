import type { Pattern } from '../types.js';
import { jsxText, regionTitle } from '../util.js';

const pattern: Pattern = {
  name: 'form/newsletter',
  group: 'form',
  score(region) {
    return /(subscribe|newsletter|email|signup|sign up)/.test(region.name.toLowerCase()) ? 150 : 0;
  },
  render({ componentName, region }) {
    const title = jsxText(regionTitle(region, 60) || 'Stay in the loop');
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <form className="mx-auto flex max-w-md flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-5 text-center shadow-sm">`,
      `      <h3 className="text-base font-semibold text-slate-900">{${title}}</h3>`,
      `      <input type="email" placeholder="you@example.com" className="rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-purple-500 focus:outline-none" />`,
      `      <button type="submit" className="rounded-md bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700">`,
      `        Subscribe`,
      `      </button>`,
      `    </form>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
