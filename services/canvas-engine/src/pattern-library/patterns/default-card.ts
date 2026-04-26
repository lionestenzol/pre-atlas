import type { Pattern } from '../types.js';
import { jsxText, regionTitle } from '../util.js';
import { LAYER_TINTS, sectionWrapper } from '../util.js';

const pattern: Pattern = {
  name: 'default/card',
  group: 'default',
  score: () => 1, // last-resort
  render({ componentName, region }) {
    const title = jsxText(regionTitle(region, 80));
    const layer = jsxText(region.layer.toUpperCase());
    const tint = LAYER_TINTS[region.layer];
    const open = sectionWrapper(region);
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      open,
      `      <div className="flex items-start justify-between text-xs uppercase tracking-[0.2em] text-slate-500">`,
      `        <span>{${layer}}{${jsxText(' · ' + (region.detection || ''))}}</span>`,
      `        <span className="rounded-full ${tint.replace('50', '100')} px-2 py-0.5 font-medium">{${jsxText('n' + region.n)}}</span>`,
      `      </div>`,
      `      <h3 className="mt-2 text-base font-semibold text-slate-900">{${title}}</h3>`,
      `    </section>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
