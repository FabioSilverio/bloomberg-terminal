export interface MarketPoint {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  currency?: string;
  source?: string;
}

export interface MarketOverviewResponse {
  asOf: string;
  degraded: boolean;
  warnings: string[];
  sections: {
    indices: MarketPoint[];
    rates: MarketPoint[];
    fx: MarketPoint[];
    commodities: MarketPoint[];
    crypto: MarketPoint[];
  };
}

const BACKEND_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';

export async function fetchMarketOverview(): Promise<MarketOverviewResponse> {
  const response = await fetch(`${BACKEND_BASE}/api/v1/market/overview`, {
    headers: {
      Accept: 'application/json'
    },
    next: {
      revalidate: 0
    }
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch market overview (${response.status})`);
  }

  return response.json() as Promise<MarketOverviewResponse>;
}
