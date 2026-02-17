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

export type AlertCondition =
  | 'price_above'
  | 'price_below'
  | 'crosses_above'
  | 'crosses_below'
  | 'percent_move_up'
  | 'percent_move_down';

export type AlertTriggerState = 'armed' | 'active' | 'cooldown' | 'triggered' | 'inactive';

export interface WatchlistAlert {
  id: number;
  enabled: boolean;
  source: string;
  condition: AlertCondition;
  threshold: number;
  oneShot: boolean;
  cooldownSeconds: number;
  triggerState: AlertTriggerState;
  active: boolean;
  inCooldown: boolean;
  lastTriggeredAt?: string;
  lastTriggerSource?: string;
  updatedAt: string;
}

export interface PriceAlert extends WatchlistAlert {
  watchlistItemId?: number;
  symbol: string;
  instrumentType?: string;
  lastConditionState?: boolean;
  lastTriggeredPrice?: number;
  lastTriggeredValue?: number;
  createdAt: string;
}

export interface PriceAlertListResponse {
  items: PriceAlert[];
}

export interface AlertTriggerEvent {
  id: number;
  alertId: number;
  symbol: string;
  condition: AlertCondition;
  threshold: number;
  triggerPrice: number;
  triggerValue?: number;
  source?: string;
  triggeredAt: string;
}

export interface AlertTriggerEventListResponse {
  items: AlertTriggerEvent[];
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
  alerts: WatchlistAlert[];
}

export interface WatchlistResponse {
  asOf: string;
  items: WatchlistItem[];
  warnings: string[];
}

export interface CreatePriceAlertPayload {
  symbol?: string;
  watchlistItemId?: number;
  condition: AlertCondition;
  threshold: number;
  enabled?: boolean;
  oneShot?: boolean;
  repeating?: boolean;
  cooldownSeconds?: number;
  source?: 'manual' | 'watchlist' | 'command' | 'system';
}

export interface UpdatePriceAlertPayload {
  symbol?: string;
  watchlistItemId?: number;
  condition?: AlertCondition;
  threshold?: number;
  enabled?: boolean;
  oneShot?: boolean;
  repeating?: boolean;
  cooldownSeconds?: number;
  source?: 'manual' | 'watchlist' | 'command' | 'system';
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

async function ensureNoContent(response: Response, fallbackMessage: string): Promise<void> {
  if (response.ok || response.status === 204) {
    return;
  }

  let detail = fallbackMessage;
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

  return ensureNoContent(response, `Failed to remove watchlist item (${response.status})`);
}

export async function removeWatchlistSymbol(symbol: string): Promise<void> {
  const response = await fetch(`${BACKEND_BASE}/api/v1/watchlist/by-symbol/${encodeURIComponent(symbol)}`, {
    method: 'DELETE'
  });

  return ensureNoContent(response, `Failed to remove ${symbol} (${response.status})`);
}

export interface FetchPriceAlertsOptions {
  symbol?: string;
  enabled?: boolean;
  status?: 'active' | 'inactive';
}

export async function fetchPriceAlerts(options: FetchPriceAlertsOptions = {}): Promise<PriceAlertListResponse> {
  const params = new URLSearchParams();
  if (options.symbol) {
    params.set('symbol', options.symbol);
  }
  if (typeof options.enabled === 'boolean') {
    params.set('enabled', String(options.enabled));
  }
  if (options.status) {
    params.set('status', options.status);
  }

  const suffix = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`${BACKEND_BASE}/api/v1/alerts${suffix}`, {
    headers: {
      Accept: 'application/json'
    },
    cache: 'no-store'
  });

  return readJson<PriceAlertListResponse>(response);
}

export async function createPriceAlert(payload: CreatePriceAlertPayload): Promise<PriceAlert> {
  const response = await fetch(`${BACKEND_BASE}/api/v1/alerts`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json'
    },
    body: JSON.stringify(payload)
  });

  return readJson<PriceAlert>(response);
}

export async function updatePriceAlert(alertId: number, payload: UpdatePriceAlertPayload): Promise<PriceAlert> {
  const response = await fetch(`${BACKEND_BASE}/api/v1/alerts/${alertId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json'
    },
    body: JSON.stringify(payload)
  });

  return readJson<PriceAlert>(response);
}

export async function removePriceAlert(alertId: number): Promise<void> {
  const response = await fetch(`${BACKEND_BASE}/api/v1/alerts/${alertId}`, {
    method: 'DELETE'
  });

  return ensureNoContent(response, `Failed to remove alert ${alertId}`);
}

export interface FetchAlertEventsOptions {
  symbol?: string;
  alertId?: number;
  afterId?: number;
  limit?: number;
}

export async function fetchAlertEvents(options: FetchAlertEventsOptions = {}): Promise<AlertTriggerEventListResponse> {
  const params = new URLSearchParams();
  if (options.symbol) {
    params.set('symbol', options.symbol);
  }
  if (typeof options.alertId === 'number') {
    params.set('alertId', String(options.alertId));
  }
  if (typeof options.afterId === 'number') {
    params.set('afterId', String(options.afterId));
  }
  if (typeof options.limit === 'number') {
    params.set('limit', String(options.limit));
  }

  const suffix = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`${BACKEND_BASE}/api/v1/alerts/events${suffix}`, {
    headers: {
      Accept: 'application/json'
    },
    cache: 'no-store'
  });

  return readJson<AlertTriggerEventListResponse>(response);
}
