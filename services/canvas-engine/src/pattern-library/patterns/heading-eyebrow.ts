import type { Pattern } from '../types.js';
import { jsxText, regionLabel } from '../util.js';

const pattern: Pattern = {
  name: 'heading/eyebrow',
  group: 'heading',
  score(region) {
    const det = region.detection;
    return (det === 'sem-h2' || det === 'sem-h3') && region.desc ? 150 : 0;
  },
  render({ componentName, region }) {
    const tag = region.detection === 'sem-h2' ? 'h2' : 'h3';
    const sizeClass = tag === 'h2' ? 'text-3xl font-semibold' : 'text-xl font-semibold';
    const title = jsxText(regionLabel(region, 'Featured', 120));
    const eyebrow = jsxText(region.desc || '');

    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <div>`,
      `      <p className="mb-2 text-xs uppercase tracking-[0.3em] text-purple-700">{${eyebrow}}</p>`,
      `      <${tag} className="${sizeClass} text-slate-900">{${title}}</${tag}>`,
      `    </div>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
