import type { Pattern } from '../types.js';
import { jsxText, regionTitle } from '../util.js';

const pattern: Pattern = {
  name: 'card/action',
  group: 'card',
  score(region) {
    return region.fetches && region.fetches.length > 0 ? 130 : 0;
  },
  render({ componentName, region }) {
    const title = jsxText(regionTitle(region, 60));
    const desc = jsxText(region.desc || 'Action card');
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <article className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">`,
      `      <h3 className="text-base font-semibold text-slate-900">{${title}}</h3>`,
      `      <p className="text-sm text-slate-600">{${desc}}</p>`,
      `      <button className="self-start rounded-md bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700">View →</button>`,
      `    </article>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
