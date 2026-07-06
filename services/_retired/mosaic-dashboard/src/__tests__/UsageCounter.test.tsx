// @vitest-environment jsdom
import { expect, test, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
import UsageCounter from '../components/UsageCounter';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const mockUsage = { ai_seconds_used: 120, free_tier_seconds: 3600, paused: false };

test('renders usage stats after fetch', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(mockUsage),
  }));
  render(<UsageCounter />);
  await waitFor(() => expect(screen.getByText('120s')).toBeDefined());
  expect(screen.getByText('/ 3600s')).toBeDefined();
});

test('shows paused badge when paused', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ ...mockUsage, paused: true }),
  }));
  render(<UsageCounter />);
  await waitFor(() => expect(screen.getByText('PAUSED')).toBeDefined());
  expect(screen.getByText('Resume')).toBeDefined();
});

test('pause button calls POST endpoint', async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(mockUsage) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ paused: true, message: 'ok' }) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ ...mockUsage, paused: true }) });
  vi.stubGlobal('fetch', fetchMock);
  render(<UsageCounter />);
  await waitFor(() => expect(screen.getByText('Pause')).toBeDefined());
  fireEvent.click(screen.getByText('Pause'));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
});

test('shows error when service unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 502, text: () => Promise.resolve('upstream_unavailable') }));
  render(<UsageCounter />);
  await waitFor(() => expect(screen.getByText('Service unavailable — backend not running')).toBeDefined());
});
