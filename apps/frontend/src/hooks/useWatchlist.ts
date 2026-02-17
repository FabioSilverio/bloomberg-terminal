'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchWatchlist } from '@/lib/api';

const DEFAULT_REFRESH_MS = Number(process.env.NEXT_PUBLIC_WATCHLIST_REFRESH_INTERVAL_MS ?? 2000);

export function useWatchlist() {
  return useQuery({
    queryKey: ['watchlist'],
    queryFn: fetchWatchlist,
    refetchInterval: Math.max(500, Number.isFinite(DEFAULT_REFRESH_MS) ? DEFAULT_REFRESH_MS : 2000)
  });
}
