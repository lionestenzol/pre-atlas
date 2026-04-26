import type { Pattern } from '../types.js';
import { jsxText, regionTitle } from '../util.js';

const pattern: Pattern = {
  name: 'clickable/button',
  group: 'clickable',
  score(region) {
    let s = 50;
    const det = region.detection || '';
    if (det === 'r7-native-interactive') s += 30;
    if (det === 'r8-event-handler-attrs') s += 20;
    if (region.bounds && region.bounds.w > 60 && region.bounds.w < 240 && region.bounds.h < 80) s += 10;
    return s;
  },
  render({ componentName, region }) {
    const label = jsxText(regionTitle(region, 40));
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <button className="inline-flex items-center justify-center rounded-md bg-purple-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-purple-700">`,
      `      {${label}}`,
      `    </button>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
