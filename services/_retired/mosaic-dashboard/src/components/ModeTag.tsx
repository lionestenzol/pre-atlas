'use client';

import type { Mode } from '@/lib/types';

const MODE_COLORS: Record<Mode, string> = {
  RECOVER: 'bg-red-500/20 text-red-400 border-red-500/30',
  CLOSURE: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  MAINTENANCE: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  BUILD: 'bg-green-500/20 text-green-400 border-green-500/30',
  COMPOUND: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  SCALE: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
};

interface ModeTagProps {
  mode: Mode;
  large?: boolean;
}

export default function ModeTag({ mode, large }: ModeTagProps) {
  const colors = MODE_COLORS[mode] ?? 'bg-zinc-700 text-zinc-300 border-zinc-600';
  const size = large ? 'text-xl px-4 py-2' : 'text-xs px-2 py-1';
  return (
    <span className={`inline-block font-mono font-bold rounded border ${colors} ${size}`}>
      {mode}
    </span>
  );
}
