'use client';

import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import { fetchIntraday, IntradayResponse, WS_INTRADAY_BASE_ENDPOINT } from '@/lib/api';

const DEFAULT_REFRESH_MS = Number(process.env.NEXT_PUBLIC_INTRADAY_REFRESH_INTERVAL_MS ?? 2000);

function normalizeIntradaySymbolForWs(symbol: string): string {
  const raw = (symbol ?? '').trim().toUpperCase();
  const slashFx = raw.match(/^([A-Z]{3})\s*\/\s*([A-Z]{3})$/);
  if (slashFx) {
    return `${slashFx[1]}${slashFx[2]}`;
  }
  return raw.replace(/\s+/g, '');
}

function resolveIntradayWsEndpoint(symbol: string): string {
  const encoded = encodeURIComponent(normalizeIntradaySymbolForWs(symbol));

  if (WS_INTRADAY_BASE_ENDPOINT) {
    const base = WS_INTRADAY_BASE_ENDPOINT.replace(/\/$/, '');
    return `${base}/${encoded}`;
  }

  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${protocol}://${window.location.host}/ws/market/intraday/${encoded}`;
  }

  return `ws://localhost:8000/ws/market/intraday/${encoded}`;
}

export type IntradayStreamStatus = 'polling' | 'connecting' | 'live';

export function useIntraday(symbol: string) {
  const queryClient = useQueryClient();
  const [streamStatus, setStreamStatus] = useState<IntradayStreamStatus>('polling');

  const query = useQuery({
    queryKey: ['intraday', symbol],
    queryFn: () => fetchIntraday(symbol),
    retry: 1,
    refetchOnWindowFocus: false,
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
