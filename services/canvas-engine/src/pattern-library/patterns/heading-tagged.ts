import type { Pattern } from '../types.js';
import { jsxText, regionTitle } from '../util.js';

const SIZE: Record<string, string> = {
  h1: 'text-4xl font-bold tracking-tight',
  h2: 'text-2xl font-semibold tracking-tight',
  h3: 'text-xl font-semibold',
  h4: 'text-lg font-medium',
  h5: 'text-base font-medium',
  h6: 'text-sm font-medium uppercase tracking-wide',
};

const pattern: Pattern = {
  name: 'heading/tagged',
  group: 'heading',
  score: () => 100, // only candidate · always wins
  render({ componentName, region }) {
    const det = region.detection || 'sem-h3';
    const tag = det.replace('sem-', '');
    const sizeClass = SIZE[tag] || SIZE.h3;
    const label = jsxText(regionTitle(region, 120));
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <${tag} className="${sizeClass} text-slate-900">`,
      `      {${label}}`,
      `    </${tag}>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
