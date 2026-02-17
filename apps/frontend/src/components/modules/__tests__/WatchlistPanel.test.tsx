import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import { WatchlistPanel } from '@/components/modules/WatchlistPanel';

vi.mock('@/lib/api', () => ({
  addWatchlistSymbol: vi.fn(),
  fetchWatchlist: vi.fn(),
  removeWatchlistItem: vi.fn()
}));

vi.mock('@/hooks/useWatchlist', () => ({
  useWatchlist: () => ({
    data: {
      asOf: new Date().toISOString(),
      warnings: [],
      items: [
        {
          id: 1,
          symbol: 'AAPL',
          displaySymbol: 'AAPL',
          instrumentType: 'equity',
          position: 1,
          createdAt: new Date().toISOString(),
          quote: {
            source: 'test-feed',
            asOf: new Date().toISOString(),
            lastPrice: 201.2,
            change: 1.5,
            changePercent: 0.75,
            volume: 1000,
            stale: false
          },
          alerts: [
            {
              id: 11,
              enabled: true,
              source: 'manual',
              condition: 'price_above',
              threshold: 200,
              oneShot: false,
              cooldownSeconds: 60,
              triggerState: 'triggered',
              active: true,
              inCooldown: true,
              updatedAt: new Date().toISOString()
            }
          ]
        }
      ]
    },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn()
  })
}));

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <WatchlistPanel />
    </QueryClientProvider>
  );
}

describe('WatchlistPanel', () => {
  it('shows triggered indicator badge for rows with fired alerts', async () => {
    renderPanel();

    expect(await screen.findByText('TRG 1')).toBeInTheDocument();
  });
});
