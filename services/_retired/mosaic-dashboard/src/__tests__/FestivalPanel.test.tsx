// @vitest-environment jsdom
import { expect, test, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
import FestivalPanel from '../components/FestivalPanel';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const mockStatus = {
  timestamp: '2026-03-26T12:00:00Z',
  mode: 'BUILD',
  risk: 'low',
  build_allowed: true,
  open_loops: 2,
  festival: { phase1: { done: 11, total: 11 }, phase2: { done: 5, total: 15 } },
};

test('renders festival progress after fetch', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(mockStatus),
  }));
  render(<FestivalPanel />);
  await waitFor(() => expect(screen.getByText('BUILD')).toBeDefined());
  expect(screen.getByText('11/11')).toBeDefined();
  expect(screen.getByText('5/15')).toBeDefined();
});

test('execute button shows result', async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(mockStatus) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ status: 'not_implemented', message: 'Claude adapter not wired' }) });
  vi.stubGlobal('fetch', fetchMock);
  render(<FestivalPanel />);
  await waitFor(() => expect(screen.getByText('Execute Next')).toBeDefined());
  fireEvent.click(screen.getByText('Execute Next'));
  await waitFor(() => expect(screen.getByText('Claude adapter not wired')).toBeDefined());
});

test('shows error when orchestrator unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 502, text: () => Promise.resolve('Bad Gateway') }));
  render(<FestivalPanel />);
  await waitFor(() => expect(screen.getByText('Service unavailable — backend not running')).toBeDefined());
});
