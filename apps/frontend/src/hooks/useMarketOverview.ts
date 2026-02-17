'use client';

import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchMarketOverview, MarketOverviewResponse, WS_OVERVIEW_ENDPOINT } from '@/lib/api';

const QUERY_KEY = ['market-overview'];

const WS_ENDPOINT =
  WS_OVERVIEW_ENDPOINT ??
  (typeof window !== 'undefined'
    ? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/market/overview`
    : 'ws://localhost:8000/ws/market/overview');

export function useMarketOverview(refreshIntervalMs: number) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: fetchMarketOverview,
    refetchInterval: Math.max(500, refreshIntervalMs)
  });

  useEffect(() => {
    let socket: WebSocket | undefined;

    try {
      socket = new WebSocket(WS_ENDPOINT);
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as MarketOverviewResponse;
          queryClient.setQueryData(QUERY_KEY, payload);
        } catch {
          // Ignore malformed payloads and keep polling path active.
        }
      };
    } catch {
      // Silent fallback to query polling.
    }

    return () => socket?.close();
  }, [queryClient]);

  return query;
}
