import type { Pattern } from '../types.js';
import { jsxText, regionLabel } from '../util.js';

const pattern: Pattern = {
  name: 'card/content',
  group: 'card',
  score: () => 100,
  render({ componentName, region }) {
    const title = jsxText(regionLabel(region, 'Card title', 60));
    const desc = region.desc ? jsxText(region.desc) : '"Card content placeholder."';
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <article className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow-md">`,
      `      <h3 className="text-base font-semibold text-slate-900">{${title}}</h3>`,
      `      <p className="text-sm text-slate-600">{${desc}}</p>`,
      `      <div className="mt-auto flex items-center justify-between text-xs text-slate-400">`,
      `        <span>n${region.n}</span>`,
      `        <a href="#" className="text-purple-700 hover:underline">read more →</a>`,
      `      </div>`,
      `    </article>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
