// @vitest-environment jsdom
import { expect, test, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import ModePanel from '../components/ModePanel';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const mockDerived = {
  mode: 'BUILD',
  risk: 'low',
  open_loops: 2,
  closure_ratio: 0.85,
  primary_order: 'build',
  build_allowed: true,
  enforcement_level: 1,
  violations_count: 0,
  overrides_count: 0,
  override_available: true,
  closures_today: 3,
  total_closures: 45,
  streak_days: 7,
  best_streak: 14,
};

beforeEach(() => {
  vi.useFakeTimers();
});

test('shows loading state initially', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
  render(<ModePanel />);
  // Panel shows title while loading
  expect(screen.getByText('Mode & Governance')).toBeDefined();
});

test('renders mode badge and stats after fetch', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ ok: true, ts: '', delta: {}, cognitive: {}, derived: mockDerived, errors: [] }),
  }));
  vi.useRealTimers();
  render(<ModePanel />);
  await waitFor(() => expect(screen.getByText('BUILD')).toBeDefined());
  expect(screen.getByText('Build Allowed')).toBeDefined();
  expect(screen.getByText('7d')).toBeDefined();
  expect(screen.getByText('85%')).toBeDefined();
});

test('shows error when upstream unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 502, text: () => Promise.resolve('Bad Gateway') }));
  vi.useRealTimers();
  render(<ModePanel />);
  await waitFor(() => expect(screen.getByText('Service unavailable — backend not running')).toBeDefined());
  expect(screen.getByText('Retry')).toBeDefined();
});

test('auto-refreshes after 30s', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ ok: true, ts: '', delta: {}, cognitive: {}, derived: mockDerived, errors: [] }),
  });
  vi.stubGlobal('fetch', fetchMock);
  render(<ModePanel />);
  // Initial fetch
  await vi.advanceTimersByTimeAsync(100);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  // After 30s
  await vi.advanceTimersByTimeAsync(30_000);
  expect(fetchMock).toHaveBeenCalledTimes(2);
});
