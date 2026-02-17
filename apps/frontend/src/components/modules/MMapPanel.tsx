'use client';

import clsx from 'clsx';
import { useMarketOverview } from '@/hooks/useMarketOverview';
import { MarketPoint } from '@/lib/api';

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

function MarketTable({ title, rows }: { title: string; rows: MarketPoint[] }) {
  return (
    <section className="border border-terminal-line bg-[#0b1119]">
      <header className="border-b border-terminal-line bg-[#101822] px-2 py-1 text-[11px] font-bold uppercase tracking-wider text-terminal-accent">
        {title}
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
  const { data, isLoading, isError, error } = useMarketOverview();

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

  return (
    <div className="flex h-full flex-col bg-terminal-panel">
      <div className="flex items-center justify-between border-b border-terminal-line px-3 py-2 text-[11px]">
        <div className="uppercase tracking-wider text-terminal-muted">As of {new Date(data.asOf).toLocaleTimeString()}</div>
        <div className={clsx('font-semibold', data.degraded ? 'text-terminal-down' : 'text-terminal-up')}>
          {data.degraded ? 'DEGRADED MODE' : 'LIVE'}
        </div>
      </div>

      {data.warnings.length > 0 && (
        <div className="border-b border-terminal-line bg-[#21150f] px-3 py-1 text-[11px] text-[#ffbc7d]">
          {data.warnings.join(' | ')}
        </div>
      )}

      <div className="grid flex-1 grid-cols-1 gap-2 overflow-auto p-2 scrollbar-thin lg:grid-cols-2">
        <MarketTable title="Indices" rows={data.sections.indices} />
        <MarketTable title="Rates" rows={data.sections.rates} />
        <MarketTable title="FX" rows={data.sections.fx} />
        <MarketTable title="Commodities" rows={data.sections.commodities} />
        <div className="lg:col-span-2">
          <MarketTable title="Crypto" rows={data.sections.crypto} />
        </div>
      </div>
    </div>
  );
}
