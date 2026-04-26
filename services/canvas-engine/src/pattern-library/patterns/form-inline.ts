import type { Pattern } from '../types.js';

const pattern: Pattern = {
  name: 'form/inline',
  group: 'form',
  score(region) {
    if (region.name.toLowerCase().includes('search')) return 150;
    if (region.bounds && region.bounds.h < 60) return 150;
    return 0;
  },
  render({ componentName }) {
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <form className="flex items-center gap-2 rounded-lg bg-white p-2 ring-1 ring-slate-200">`,
      `      <input type="text" placeholder="Search..." className="flex-1 rounded-md border border-slate-200 px-3 py-2 text-sm placeholder:text-slate-400 focus:border-purple-500 focus:outline-none" />`,
      `      <button type="submit" className="rounded-md bg-purple-600 px-3 py-2 text-sm font-medium text-white hover:bg-purple-700">`,
      `        Go`,
      `      </button>`,
      `    </form>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
