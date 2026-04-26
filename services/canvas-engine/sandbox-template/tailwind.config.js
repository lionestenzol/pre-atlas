// canvas-engine sandbox template · Tailwind config
// safelist is exhaustive for the Phase 3 deterministic stub's class vocabulary.
// (Vite boots before generated files exist, so content-scanning misses them on
// first compile · safelist guarantees these utilities are always emitted.)
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  safelist: [
    // layout
    'min-h-screen', 'mx-auto', 'flex', 'w-full', 'max-w-6xl', 'flex-col', 'flex-row',
    'grid', 'md:grid-cols-2', 'gap-4', 'gap-6',
    'items-start', 'items-center', 'justify-between', 'justify-center',
    // spacing
    'p-5', 'p-6', 'px-3', 'px-4', 'py-1', 'py-8', 'pl-5',
    'mt-2', 'mt-4', 'space-y-1',
    // surfaces
    'bg-slate-100', 'bg-white', 'bg-white/80', 'bg-gray-50',
    'bg-purple-50', 'bg-amber-50', 'bg-sky-50', 'bg-emerald-50', 'bg-rose-50',
    // edit-loop tint targets · any Tailwind hue at the soft tint shades
    {
      pattern:
        /^bg-(red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|slate|gray|zinc|neutral|stone)-(50|100|200)$/,
    },
    // borders / shadows
    'border', 'border-slate-200', 'rounded-2xl', 'rounded-3xl', 'rounded-full',
    'shadow-sm', 'ring-1', 'ring-slate-200',
    // typography
    'font-semibold', 'font-medium', 'font-bold',
    'text-xs', 'text-sm', 'text-xl', 'text-3xl',
    'uppercase', 'tracking-[0.2em]', 'tracking-[0.3em]', 'list-disc',
    // colors
    'text-slate-500', 'text-slate-600', 'text-slate-700', 'text-slate-800', 'text-slate-900',
    'text-gray-900', 'text-gray-600',
  ],
  theme: { extend: {} },
  plugins: [],
};
