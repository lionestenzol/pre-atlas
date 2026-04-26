import type { Pattern } from '../types.js';

const pattern: Pattern = {
  name: 'landmark/nav',
  group: 'landmark',
  score(region) {
    return region.detection === 'sem-nav' ? 150 : 0;
  },
  render({ componentName }) {
    return [
      `export default function ${componentName}() {`,
      `  return (`,
      `    <nav className="flex items-center gap-6 border-b border-slate-200 bg-white px-6 py-3 text-sm">`,
      `      <a href="#" className="text-slate-600 hover:text-slate-900">Home</a>`,
      `      <a href="#" className="text-slate-600 hover:text-slate-900">Docs</a>`,
      `      <a href="#" className="text-slate-600 hover:text-slate-900">Pricing</a>`,
      `      <a href="#" className="text-slate-600 hover:text-slate-900">About</a>`,
      `      <a href="#" className="text-slate-600 hover:text-slate-900">Contact</a>`,
      `    </nav>`,
      `  );`,
      `}`,
    ].join('\n');
  },
};

export default pattern;
