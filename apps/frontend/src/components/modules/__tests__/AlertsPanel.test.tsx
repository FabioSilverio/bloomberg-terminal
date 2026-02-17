import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import { AlertsPanel } from '@/components/modules/AlertsPanel';
import { useTerminalStore } from '@/store/useTerminalStore';

const fetchPriceAlerts = vi.fn();
const fetchWatchlist = vi.fn();

vi.mock('@/lib/api', () => ({
  fetchPriceAlerts: (...args: unknown[]) => fetchPriceAlerts(...args),
  fetchWatchlist: (...args: unknown[]) => fetchWatchlist(...args),
  createPriceAlert: vi.fn(),
  updatePriceAlert: vi.fn(),
  removePriceAlert: vi.fn()
}));

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false }
    }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AlertsPanel panelId="alrt-test" initialSymbol="AAPL" />
    </QueryClientProvider>
  );
}

describe('AlertsPanel', () => {
  beforeEach(() => {
    useTerminalStore.setState({
      commandFeedback: '',
      alertSoundEnabled: true
    });

    fetchWatchlist.mockResolvedValue({ asOf: new Date().toISOString(), items: [], warnings: [] });
    fetchPriceAlerts.mockResolvedValue({
      items: [
        {
          id: 301,
          symbol: 'AAPL',
          source: 'manual',
          condition: 'price_above',
          threshold: 210,
          enabled: true,
          oneShot: false,
          cooldownSeconds: 60,
          triggerState: 'triggered',
          active: true,
          inCooldown: false,
          updatedAt: new Date().toISOString(),
          createdAt: new Date().toISOString()
        }
      ]
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders active alerts and triggered state badge', async () => {
    renderPanel();

    expect(await screen.findByText('#301')).toBeInTheDocument();
    expect(screen.getByText('triggered')).toBeInTheDocument();
  });
});
