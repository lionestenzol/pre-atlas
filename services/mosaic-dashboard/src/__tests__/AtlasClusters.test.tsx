// @vitest-environment jsdom
import { expect, test, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import AtlasClusters from '../components/AtlasClusters';

// Mock react-plotly.js (heavy dep, not needed for unit tests)
vi.mock('react-plotly.js', () => ({
  default: (props: Record<string, unknown>) => <div data-testid="plotly-chart" data-traces={JSON.stringify(props.data)} />,
}));

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const mockIdeas = {
  metadata: { generated_at: '', total_ideas: 2, reference_date: '', tier_breakdown: { execute_now: 1, next_up: 1 }, max_priority: 0.9, avg_priority: 0.5 },
  tiers: {
    execute_now: [{
      canonical_id: 'c1', canonical_title: 'Idea One', priority_score: 0.9,
      priority_breakdown: { frequency: 0.8, recency: 0.7, alignment: 0.9, feasibility: 0.6, compounding: 0.5 },
      category: 'ai', status: 'idea', complexity: 'medium', mention_count: 5, alignment_score: 0.85, dependencies: [], child_ideas: [],
    }],
    next_up: [{
      canonical_id: 'c2', canonical_title: 'Idea Two', priority_score: 0.6,
      priority_breakdown: { frequency: 0.5, recency: 0.4, alignment: 0.7, feasibility: 0.8, compounding: 0.3 },
      category: 'saas', status: 'idea', complexity: 'small', mention_count: 2, alignment_score: 0.7, dependencies: [], child_ideas: [],
    }],
  },
};

test('renders Plotly chart after data loads', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(mockIdeas),
  }));
  render(<AtlasClusters />);
  await waitFor(() => expect(screen.getByTestId('plotly-chart')).toBeDefined());
});

test('shows error when ideas endpoint returns 404', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404, text: () => Promise.resolve('idea_registry.json not found') }));
  render(<AtlasClusters />);
  await waitFor(() => expect(screen.getByText('idea_registry.json not found')).toBeDefined());
});

test('shows empty state when no ideas', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ metadata: { total_ideas: 0 }, tiers: {} }),
  }));
  render(<AtlasClusters />);
  await waitFor(() => expect(screen.getByText('No ideas data available')).toBeDefined());
});
