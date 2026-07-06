'use client';

import { useState, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import Panel from './Panel';
import { getIdeas } from '@/lib/api';
import type { IdeaItem } from '@/lib/types';

// Lazy-load Plotly (large bundle, client-only)
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const TIER_COLORS: Record<string, string> = {
  execute_now: '#22c55e',
  next_up: '#3b82f6',
  backlog: '#a1a1aa',
  archive: '#52525b',
};

interface PlotIdea extends IdeaItem {
  tier: string;
}

export default function AtlasClusters() {
  const [ideas, setIdeas] = useState<PlotIdea[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await getIdeas();
      const flat: PlotIdea[] = [];
      for (const [tier, items] of Object.entries(data.tiers)) {
        for (const item of items) {
          flat.push({ ...item, tier });
        }
      }
      setIdeas(flat);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ideas data unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Group by tier for Plotly traces
  const tiers = [...new Set(ideas.map(i => i.tier))];
  const traces = tiers.map(tier => {
    const items = ideas.filter(i => i.tier === tier);
    return {
      x: items.map(i => i.alignment_score),
      y: items.map(i => i.priority_score),
      text: items.map(i => i.canonical_title),
      marker: {
        color: TIER_COLORS[tier] ?? '#71717a',
        size: items.map(i => Math.max(6, Math.min(20, i.mention_count * 2))),
      },
      mode: 'markers' as const,
      type: 'scatter' as const,
      name: tier.replace('_', ' '),
      hovertemplate: '%{text}<br>Alignment: %{x:.2f}<br>Priority: %{y:.2f}<extra></extra>',
    };
  });

  return (
    <Panel title="Atlas Clusters" loading={loading} error={error} onRetry={load} className="xl:col-span-2">
      {ideas.length > 0 ? (
        <Plot
          data={traces}
          layout={{
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: { color: '#a1a1aa', size: 11 },
            margin: { t: 10, r: 10, b: 40, l: 50 },
            xaxis: {
              title: 'Alignment',
              gridcolor: '#27272a',
              zerolinecolor: '#3f3f46',
              range: [0, 1],
            },
            yaxis: {
              title: 'Priority',
              gridcolor: '#27272a',
              zerolinecolor: '#3f3f46',
              range: [0, 1],
            },
            legend: { orientation: 'h', y: -0.15, font: { size: 10 } },
            showlegend: true,
            autosize: true,
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: '100%', height: '300px' }}
        />
      ) : (
        <p className="text-sm text-zinc-500">No ideas data available</p>
      )}
    </Panel>
  );
}
