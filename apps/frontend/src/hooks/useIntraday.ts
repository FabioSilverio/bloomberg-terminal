'use client';

import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import { fetchIntraday, IntradayResponse } from '@/lib/api';

const DEFAULT_REFRESH_MS = Number(process.env.NEXT_PUBLIC_INTRADAY_REFRESH_INTERVAL_MS ?? 2000);

function resolveIntradayWsEndpoint(symbol: string): string {
  const encoded = encodeURIComponent(symbol);

  if (process.env.NEXT_PUBLIC_INTRADAY_WS_BASE_URL) {
    const base = process.env.NEXT_PUBLIC_INTRADAY_WS_BASE_URL.replace(/\/$/, '');
    return `${base}/${encoded}`;
  }

  const overviewEndpoint = process.env.NEXT_PUBLIC_WS_BASE_URL;
  if (overviewEndpoint) {
    const root = overviewEndpoint.replace(/\/ws\/market\/overview\/?$/i, '');
    return `${root}/ws/market/intraday/${encoded}`;
  }

  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${protocol}://${window.location.host}/ws/market/intraday/${encoded}`;
  }

  return `ws://localhost/ws/market/intraday/${encoded}`;
}

export type IntradayStreamStatus = 'polling' | 'connecting' | 'live';

export function useIntraday(symbol: string) {
  const queryClient = useQueryClient();
  const [streamStatus, setStreamStatus] = useState<IntradayStreamStatus>('polling');

  const query = useQuery({
    queryKey: ['intraday', symbol],
    queryFn: () => fetchIntraday(symbol),
    refetchInterval: Math.max(500, Number.isFinite(DEFAULT_REFRESH_MS) ? DEFAULT_REFRESH_MS : 2000)
  });

  useEffect(() => {
    if (!symbol) {
      setStreamStatus('polling');
      return;
    }

    let socket: WebSocket | undefined;
    let isUnmounted = false;

    try {
      socket = new WebSocket(resolveIntradayWsEndpoint(symbol));
      setStreamStatus('connecting');

      socket.onopen = () => {
        if (!isUnmounted) {
          setStreamStatus('live');
        }
      };

      socket.onclose = () => {
        if (!isUnmounted) {
          setStreamStatus('polling');
        }
      };

      socket.onerror = () => {
        if (!isUnmounted) {
          setStreamStatus('polling');
        }
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as IntradayResponse | { error?: string };
          if ('error' in payload) {
            return;
          }
          queryClient.setQueryData(['intraday', symbol], payload);
        } catch {
          // Keep polling path active.
        }
      };
    } catch {
      setStreamStatus('polling');
    }

    return () => {
      isUnmounted = true;
      setStreamStatus('polling');
      socket?.close();
    };
  }, [queryClient, symbol]);

  return {
    ...query,
    streamStatus
  };
}
