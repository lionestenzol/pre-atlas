import type { Pattern } from '../types.js';
import { jsxText, regionLabel } from '../util.js';

const pattern: Pattern = {
  name: 'list/tags',
  group: 'list',
  score(region) {
    const shortName = region.name.length <= 30;
    const compactHeight = !region.bounds || region.bounds.h < 60;
    return shortName && compactHeight ? 130 : 0;
  },
  render({ componentName, region }) {
    const title = jsxText(regionLabel(region, 'Items', 60));
    return [
      `export default function ${componentName}() {`,
      `  const tags = ['Tag-1', 'Tag-2', 'Tag-3', 'Tag-4', 'Tag-5'];`,
      `  return (`,
      `    <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">`,
      `      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{${title}}</h3>`,
      `      <div className="mt-3 flex flex-wrap gap-2">`,
      `        {tags.map((tag) => (`,
      `          <span key={tag} className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">`,
      `            {tag}`,
      `          </span>`,
      `        ))}`,
      `      </div>`,
      `    </section>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
