import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import { IntradayPanel } from '@/components/modules/IntradayPanel';

const fetchPriceAlerts = vi.fn();

vi.mock('lightweight-charts', () => ({
  ColorType: { Solid: 0 },
  createChart: () => ({
    addLineSeries: () => ({ setData: vi.fn() }),
    applyOptions: vi.fn(),
    timeScale: () => ({ fitContent: vi.fn() }),
    remove: vi.fn()
  })
}));

vi.mock('@/hooks/useIntraday', () => ({
  useIntraday: () => ({
    data: {
      symbol: 'USDBRL',
      displaySymbol: 'USD/BRL',
      instrumentType: 'fx',
      source: 'test-feed',
      asOf: new Date().toISOString(),
      lastPrice: 5.1,
      change: 0.03,
      changePercent: 0.6,
      volume: 1234,
      stale: false,
      warnings: [],
      points: [
        {
          time: new Date().toISOString(),
          price: 5.1,
          volume: 1234
        }
      ]
    },
    isLoading: false,
    isError: false,
    error: null,
    streamStatus: 'live'
  })
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchPriceAlerts: (...args: unknown[]) => fetchPriceAlerts(...args)
  };
});

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <IntradayPanel panelId="intra-test" initialSymbol="USD/BRL" />
    </QueryClientProvider>
  );
}

describe('IntradayPanel', () => {
  beforeEach(() => {
    fetchPriceAlerts.mockResolvedValue({ items: [] });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders intraday load path with beginner helper text', async () => {
    renderPanel();

    expect(await screen.findByText('Examples: USD/BRL, USDBRL, BRLUSD, AAPL, BTCUSD')).toBeInTheDocument();
    expect(screen.getByDisplayValue('USD/BRL')).toBeInTheDocument();
    expect(screen.getByText('live')).toBeInTheDocument();
  });
});
