export interface MarketPoint {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  currency?: string;
  source?: string;
  asOf?: string;
}

export interface MarketSectionMeta {
  source?: string;
  sources: string[];
  asOf?: string;
  loaded: number;
  expected: number;
  stale: boolean;
}

export interface MarketOverviewResponse {
  asOf: string;
  degraded: boolean;
  banner?: string;
  warnings: string[];
  sections: {
    indices: MarketPoint[];
    rates: MarketPoint[];
    fx: MarketPoint[];
    commodities: MarketPoint[];
    crypto: MarketPoint[];
  };
  sectionMeta: {
    indices: MarketSectionMeta;
    rates: MarketSectionMeta;
    fx: MarketSectionMeta;
    commodities: MarketSectionMeta;
    crypto: MarketSectionMeta;
  };
}

export interface IntradayPoint {
  time: string;
  price: number;
  volume?: number;
}

export interface IntradayResponse {
  symbol: string;
  displaySymbol: string;
  instrumentType: string;
  source: string;
  asOf: string;
  lastPrice: number;
  change: number;
  changePercent: number;
  volume?: number;
  currency?: string;
  stale: boolean;
  freshnessSeconds?: number;
  warnings: string[];
  points: IntradayPoint[];
}

export interface WatchlistQuote {
  source: string;
  asOf: string;
  lastPrice: number;
  change: number;
  changePercent: number;
  volume?: number;
  currency?: string;
  stale: boolean;
  freshnessSeconds?: number;
}

export interface WatchlistItem {
  id: number;
  symbol: string;
  displaySymbol: string;
  instrumentType: string;
  position: number;
  createdAt: string;
  quote?: WatchlistQuote;
}

export interface WatchlistResponse {
  asOf: string;
  items: WatchlistItem[];
  warnings: string[];
}

const BACKEND_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;

    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload?.detail) {
        detail = payload.detail;
      }
    } catch {
      // noop
    }

    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

export async function fetchMarketOverview(): Promise<MarketOverviewResponse> {
  const response = await fetch(`${BACKEND_BASE}/api/v1/market/overview`, {
    headers: {
      Accept: 'application/json'
    },
    cache: 'no-store'
  });

  return readJson<MarketOverviewResponse>(response);
}

export async function fetchIntraday(symbol: string): Promise<IntradayResponse> {
  const response = await fetch(`${BACKEND_BASE}/api/v1/market/intraday/${encodeURIComponent(symbol)}`, {
    headers: {
      Accept: 'application/json'
    },
    cache: 'no-store'
  });

  return readJson<IntradayResponse>(response);
}

export async function fetchWatchlist(): Promise<WatchlistResponse> {
  const response = await fetch(`${BACKEND_BASE}/api/v1/watchlist`, {
    headers: {
      Accept: 'application/json'
    },
    cache: 'no-store'
  });

  return readJson<WatchlistResponse>(response);
}

export async function addWatchlistSymbol(symbol: string): Promise<WatchlistItem> {
  const response = await fetch(`${BACKEND_BASE}/api/v1/watchlist`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json'
    },
    body: JSON.stringify({ symbol })
  });

  return readJson<WatchlistItem>(response);
}

export async function removeWatchlistItem(itemId: number): Promise<void> {
  const response = await fetch(`${BACKEND_BASE}/api/v1/watchlist/${itemId}`, {
    method: 'DELETE'
  });

  if (!response.ok && response.status !== 204) {
    throw new Error(`Failed to remove watchlist item (${response.status})`);
  }
}

export async function removeWatchlistSymbol(symbol: string): Promise<void> {
  const response = await fetch(`${BACKEND_BASE}/api/v1/watchlist/by-symbol/${encodeURIComponent(symbol)}`, {
    method: 'DELETE'
  });

  if (!response.ok && response.status !== 204) {
    throw new Error(`Failed to remove ${symbol} (${response.status})`);
  }
}
