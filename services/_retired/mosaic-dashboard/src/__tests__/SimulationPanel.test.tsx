// @vitest-environment jsdom
import { expect, test, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
import SimulationPanel from '../components/SimulationPanel';

// Mock d3 to avoid SVG rendering issues in jsdom
vi.mock('d3', () => ({
  select: vi.fn(() => ({
    selectAll: vi.fn().mockReturnThis(),
    remove: vi.fn().mockReturnThis(),
    attr: vi.fn().mockReturnThis(),
    append: vi.fn().mockReturnThis(),
    call: vi.fn().mockReturnThis(),
    datum: vi.fn().mockReturnThis(),
  })),
  scaleLinear: vi.fn(() => {
    const scale = (v: number) => v;
    scale.domain = vi.fn().mockReturnValue(scale);
    scale.range = vi.fn().mockReturnValue(scale);
    return scale;
  }),
  axisBottom: vi.fn(() => vi.fn()),
  axisLeft: vi.fn(() => vi.fn()),
  line: vi.fn(() => {
    const l = vi.fn();
    l.x = vi.fn().mockReturnValue(l);
    l.y = vi.fn().mockReturnValue(l);
    return l;
  }),
}));

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

test('shows form with topic input and start button', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ simulations: [] }),
  }));
  render(<SimulationPanel />);
  await waitFor(() => expect(screen.getByPlaceholderText('Simulation topic...')).toBeDefined());
  expect(screen.getByText('Run Simulation')).toBeDefined();
});

test('start button disabled when topic empty', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ simulations: [] }),
  }));
  render(<SimulationPanel />);
  await waitFor(() => expect(screen.getByText('Run Simulation')).toBeDefined());
  const btn = screen.getByText('Run Simulation') as HTMLButtonElement;
  expect(btn.disabled).toBe(true);
});

test('submitting starts simulation', async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ simulations: [] }) })
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ simulation_id: 'sim-1', status: 'started', topic: 'test', agent_count: 5, tick_count: 10 }),
    });
  vi.stubGlobal('fetch', fetchMock);
  render(<SimulationPanel />);
  await waitFor(() => expect(screen.getByText('Run Simulation')).toBeDefined());
  fireEvent.change(screen.getByPlaceholderText('Simulation topic...'), { target: { value: 'test topic' } });
  fireEvent.click(screen.getByText('Run Simulation'));
  await waitFor(() => expect(screen.getByText('started')).toBeDefined());
});

test('shows error when MiroFish unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 502, text: () => Promise.resolve('MiroFish down') }));
  render(<SimulationPanel />);
  await waitFor(() => expect(screen.getByText('Service unavailable — backend not running')).toBeDefined());
});
