'use client';

import { type ReactNode } from 'react';

interface PanelProps {
  title: string;
  children: ReactNode;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  className?: string;
}

export default function Panel({ title, children, loading, error, onRetry, className }: PanelProps) {
  return (
    <div className={`bg-zinc-900 border border-zinc-800 rounded-xl p-6 ${className ?? ''}`}>
      <h2 className="text-lg font-semibold text-zinc-100 mb-4">{title}</h2>
      {loading ? (
        <div className="space-y-3 animate-pulse">
          <div className="h-4 bg-zinc-800 rounded w-3/4" />
          <div className="h-4 bg-zinc-800 rounded w-1/2" />
          <div className="h-4 bg-zinc-800 rounded w-2/3" />
        </div>
      ) : error ? (
        <div className="text-red-400 text-sm">
          <p>{error}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-2 text-xs text-zinc-400 hover:text-zinc-200 underline"
            >
              Retry
            </button>
          )}
        </div>
      ) : (
        children
      )}
    </div>
  );
}
