'use client';

import { useEffect } from 'react';
import clsx from 'clsx';

import { useMarketOverview } from '@/hooks/useMarketOverview';
import { MarketPoint, MarketSectionMeta } from '@/lib/api';
import { useTerminalStore } from '@/store/useTerminalStore';

const EXPECTED_COUNTS = {
  indices: 4,
  rates: 3,
  fx: 3,
  commodities: 4,
  crypto: 3
} as const;

const MMAP_REFRESH_OPTIONS = [2000, 5000, 10000] as const;
const MMAP_REFRESH_STORAGE_KEY = 'openbloom:mmap-refresh-ms';

function PriceCell({ value }: { value: number }) {
  return <span className="font-semibold text-[#dce7f7]">{value.toLocaleString(undefined, { maximumFractionDigits: 4 })}</span>;
}

function ChangeCell({ point }: { point: MarketPoint }) {
  const positive = point.change >= 0;
  return (
    <span className={clsx('font-semibold', positive ? 'text-terminal-up' : 'text-terminal-down')}>
      {positive ? '+' : ''}
      {point.change.toFixed(2)} ({positive ? '+' : ''}
      {point.changePercent.toFixed(2)}%)
    </span>
  );
}

function MarketTable({ title, rows, meta }: { title: string; rows: MarketPoint[]; meta?: MarketSectionMeta }) {
  return (
    <section className="border border-terminal-line bg-[#0b1119]">
      <header className="flex items-center justify-between border-b border-terminal-line bg-[#101822] px-2 py-1 text-[11px] font-bold uppercase tracking-wider text-terminal-accent">
        <span>{title}</span>
        {meta?.source && <span className="text-[10px] font-medium normal-case text-terminal-muted">{meta.source}</span>}
      </header>
      <div className="max-h-64 overflow-auto scrollbar-thin">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wide text-terminal-muted">
              <th className="px-2 py-1">Symbol</th>
              <th className="px-2 py-1">Name</th>
              <th className="px-2 py-1 text-right">Last</th>
              <th className="px-2 py-1 text-right">Chg</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.symbol} className="border-t border-[#152033] hover:bg-[#10192a]">
                <td className="px-2 py-1 font-semibold text-[#e4edf9]">{row.symbol}</td>
                <td className="px-2 py-1 text-[#a4b2c6]">{row.name}</td>
                <td className="px-2 py-1 text-right">
                  <PriceCell value={row.price} />
                </td>
                <td className="px-2 py-1 text-right">
                  <ChangeCell point={row} />
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td className="px-2 py-3 text-terminal-muted" colSpan={4}>
                  No data available.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function MMapPanel() {
  const mmapRefreshMs = useTerminalStore((state) => state.mmapRefreshMs);
  const setMmapRefreshMs = useTerminalStore((state) => state.setMmapRefreshMs);
  const { data, isLoading, isError, error } = useMarketOverview(mmapRefreshMs);

  useEffect(() => {
    window.localStorage.setItem(MMAP_REFRESH_STORAGE_KEY, String(mmapRefreshMs));
  }, [mmapRefreshMs]);

  if (isLoading) {
    return <div className="p-3 text-sm text-terminal-muted">Loading market overview...</div>;
  }

  if (isError || !data) {
    return (
      <div className="p-3 text-sm text-terminal-down">
        Failed to load MMAP data: {error instanceof Error ? error.message : 'Unknown error'}
      </div>
    );
  }

  const totalExpected = Object.values(EXPECTED_COUNTS).reduce((acc, value) => acc + value, 0);
  const totalLoaded =
    data.sections.indices.length +
    data.sections.rates.length +
    data.sections.fx.length +
    data.sections.commodities.length +
    data.sections.crypto.length;

  const bannerText =
    data.banner ??
    (data.degraded ? `Degraded mode (${totalLoaded}/${totalExpected} instruments loaded).` : undefined);

  return (
    <div className="flex h-full flex-col bg-terminal-panel">
      <div className="flex items-center justify-between border-b border-terminal-line px-3 py-2 text-[11px]">
        <div className="flex items-center gap-2 uppercase tracking-wider text-terminal-muted">
          <span>As of {new Date(data.asOf).toLocaleTimeString()}</span>
          <span className="text-[10px] text-[#7c8ea7]">UI {Math.round(mmapRefreshMs / 1000)}s</span>
        </div>

        <div className="flex items-center gap-3">
          <label className="text-[10px] uppercase text-terminal-muted">
            Refresh
            <select
              value={mmapRefreshMs}
              onChange={(event) => setMmapRefreshMs(Number(event.target.value))}
              className="ml-1 border border-terminal-line bg-[#070c13] px-1 py-0.5 text-[10px] text-[#d7e2f0]"
            >
              {MMAP_REFRESH_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {Math.round(option / 1000)}s
                </option>
              ))}
            </select>
          </label>

          <div className={clsx('font-semibold', data.degraded ? 'text-terminal-down' : 'text-terminal-up')}>
            {data.degraded ? 'DEGRADED' : 'LIVE'}
          </div>
        </div>
      </div>

      {bannerText && (
        <div className="border-b border-terminal-line bg-[#21150f] px-3 py-2 text-[11px] text-[#ffbc7d]">
          <div className="font-semibold">{bannerText}</div>
          <div className="mt-1 text-[#ffd5a8]">{totalLoaded}/{totalExpected} instruments loaded.</div>
        </div>
      )}

      {data.warnings.length > 0 && (
        <div className="border-b border-terminal-line bg-[#1d1310] px-3 py-1 text-[11px] text-[#ffc48a]">
          <ul className="list-disc space-y-0.5 pl-4">
            {data.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid flex-1 grid-cols-1 gap-2 overflow-auto p-2 scrollbar-thin lg:grid-cols-2">
        <MarketTable title="Indices" rows={data.sections.indices} meta={data.sectionMeta?.indices} />
        <MarketTable title="Rates" rows={data.sections.rates} meta={data.sectionMeta?.rates} />
        <MarketTable title="FX" rows={data.sections.fx} meta={data.sectionMeta?.fx} />
        <MarketTable title="Commodities" rows={data.sections.commodities} meta={data.sectionMeta?.commodities} />
        <div className="lg:col-span-2">
          <MarketTable title="Crypto" rows={data.sections.crypto} meta={data.sectionMeta?.crypto} />
        </div>
      </div>
    </div>
  );
}
