import type { Pattern } from '../types.js';
import { jsxText } from '../util.js';

const pattern: Pattern = {
  name: 'card/stat',
  group: 'card',
  score(region) {
    return /^[\d.,\-+%$]/.test(region.name) || region.name.length <= 12 ? 150 : 0;
  },
  render({ componentName, region }) {
    const value = jsxText(region.name);
    const label = jsxText(region.desc || 'metric');
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <article className="flex flex-col gap-1 rounded-2xl border border-slate-200 bg-white p-5 text-center shadow-sm">`,
      `      <div className="text-4xl font-bold tracking-tight text-purple-700">{${value}}</div>`,
      `      <div className="text-xs uppercase tracking-wider text-slate-500">{${label}}</div>`,
      `    </article>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
