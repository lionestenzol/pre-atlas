import type { Pattern } from '../types.js';
import { jsxText, regionTitle } from '../util.js';

const pattern: Pattern = {
  name: 'clickable/link',
  group: 'clickable',
  score(region) {
    let s = 60;
    const det = region.detection || '';
    if (det === 'r12-cursor-pointer') s += 25;
    if (det === 'r9-aria-role') s += 10;
    // smaller bounds = more link-like
    if (region.bounds && region.bounds.h < 36) s += 10;
    return s;
  },
  render({ componentName, region }) {
    const label = jsxText(regionTitle(region, 60));
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <a href="#" className="text-sm font-medium text-purple-700 underline-offset-4 hover:underline">`,
      `      {${label}}`,
      `    </a>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
