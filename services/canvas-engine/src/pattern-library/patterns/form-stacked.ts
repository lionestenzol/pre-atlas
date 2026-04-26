import type { Pattern } from '../types.js';
import { jsxText, regionTitle } from '../util.js';

const pattern: Pattern = {
  name: 'form/stacked',
  group: 'form',
  score: () => 100,
  render({ componentName, region }) {
    const title = jsxText(regionTitle(region, 60));
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <form className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">`,
      `      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{${title}}</h3>`,
      `      <label className="flex flex-col gap-1 text-xs uppercase tracking-wide text-slate-500">`,
      `        Search`,
      `        <input type="text" placeholder="Search…" className="rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-purple-500 focus:outline-none" />`,
      `      </label>`,
      `      <button type="submit" className="self-start rounded-md bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700">`,
      `        Submit`,
      `      </button>`,
      `    </form>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
