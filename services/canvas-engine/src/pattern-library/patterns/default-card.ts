import type { Pattern } from '../types.js';
import { jsxText, regionLabel, renderBadgeHeader, sectionWrapper } from '../util.js';

const pattern: Pattern = {
  name: 'default/card',
  group: 'default',
  score: () => 1, // last-resort
  render({ componentName, region }) {
    const title = jsxText(regionLabel(region, 'Item', 80));
    const open = sectionWrapper(region);
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      open,
      renderBadgeHeader(region),
      `      <h3 className="mt-2 text-base font-semibold text-slate-900">{${title}}</h3>`,
      `    </section>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
