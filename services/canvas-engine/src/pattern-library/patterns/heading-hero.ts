import type { Pattern } from '../types.js';
import { jsxText, regionLabel } from '../util.js';

const pattern: Pattern = {
  name: 'heading/hero',
  group: 'heading',
  score(region) {
    return region.detection === 'sem-h1' ? 200 : 0;
  },
  render({ componentName, region }) {
    const title = jsxText(regionLabel(region, 'Welcome', 120));
    const eyebrow = region.desc
      ? `      <p className="text-xs uppercase tracking-[0.3em] text-purple-700">{${jsxText(region.desc)}}</p>`
      : '';

    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <div className="flex flex-col items-center gap-2 py-6 text-center">`,
      eyebrow,
      `      <h1 className="text-5xl font-bold tracking-tight text-slate-900">{${title}}</h1>`,
      `    </div>`,
      `  );`,
      `}`,
    ].filter(Boolean).join('\n');
  },
};

export default pattern;
