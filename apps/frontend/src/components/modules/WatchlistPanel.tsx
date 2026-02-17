'use client';

import React, { FormEvent, useState } from 'react';
import clsx from 'clsx';
import { useQueryClient } from '@tanstack/react-query';

import { addWatchlistSymbol, fetchWatchlist, removeWatchlistItem, WatchlistItem } from '@/lib/api';
import { normalizeSymbolToken } from '@/lib/modules';
import { useWatchlist } from '@/hooks/useWatchlist';
import { useTerminalStore } from '@/store/useTerminalStore';

function formatValue(value: number | undefined): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--';
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function summarizeAlertState(item: WatchlistItem): { label: string; className: string } {
  if (!item.alerts || item.alerts.length === 0) {
    return {
      label: 'NONE',
      className: 'border-terminal-line bg-[#121b2a] text-terminal-accent'
    };
  }

  const triggered = item.alerts.some((alert) => alert.triggerState === 'triggered');
  if (triggered) {
    return {
      label: `TRG ${item.alerts.length}`,
      className: 'border-[#8f7c2d] bg-[#2a2410] text-[#ffdf7a]'
    };
  }

  const active = item.alerts.filter((alert) => alert.enabled).length;
  if (active > 0) {
    return {
      label: `ARM ${active}`,
      className: 'border-[#3f6e4f] bg-[#112419] text-[#8de8b2]'
    };
  }

  return {
    label: `OFF ${item.alerts.length}`,
    className: 'border-[#4c3940] bg-[#1d1417] text-[#f4b6c4]'
  };
}

export function WatchlistPanel() {
  const [symbolInput, setSymbolInput] = useState('AAPL');
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const openModule = useTerminalStore((state) => state.openModule);
  const setCommandFeedback = useTerminalStore((state) => state.setCommandFeedback);

  const { data, isLoading, isError, error, refetch } = useWatchlist();

  const refreshWatchlist = async () => {
    await queryClient.invalidateQueries({ queryKey: ['watchlist'] });
    return queryClient.fetchQuery({
      queryKey: ['watchlist'],
      queryFn: fetchWatchlist
    });
  };

  const onAdd = async (event: FormEvent) => {
    event.preventDefault();
    const symbol = normalizeSymbolToken(symbolInput);
    if (!symbol) {
      setCommandFeedback('WL ADD requires a symbol. Examples: AAPL, EURUSD, GBP/JPY.');
      return;
    }

    setBusyKey('add');
    try {
      await addWatchlistSymbol(symbol);
      const snapshot = await refreshWatchlist();
      const persisted = snapshot.items.some((item) => item.symbol === symbol);
      if (!persisted) {
        throw new Error(`Watchlist add validation failed for ${symbol}.`);
      }

      setCommandFeedback(`Added ${symbol} to watchlist`);
      setSymbolInput(symbol);
    } catch (requestError) {
      setCommandFeedback(requestError instanceof Error ? requestError.message : 'Failed to add watchlist symbol');
    } finally {
      setBusyKey(null);
    }
  };

  const onRemove = async (itemId: number, symbol: string) => {
    setBusyKey(`rm-${itemId}`);
    try {
      await removeWatchlistItem(itemId);
      const snapshot = await refreshWatchlist();
      const persisted = snapshot.items.some((item) => item.symbol === symbol);
      if (persisted) {
        throw new Error(`Watchlist remove validation failed for ${symbol}.`);
      }

      setCommandFeedback(`Removed ${symbol} from watchlist`);
    } catch (requestError) {
      setCommandFeedback(requestError instanceof Error ? requestError.message : 'Failed to remove watchlist symbol');
    } finally {
      setBusyKey(null);
    }
  };

  const onOpenIntra = (item: WatchlistItem) => {
    openModule('INTRA', { symbol: item.symbol });
    setCommandFeedback(`Opened INTRA ${item.symbol}`);
  };

  const onOpenAlerts = (item: WatchlistItem) => {
    openModule('ALRT', { symbol: item.symbol });
    setCommandFeedback(`Opened ALRT ${item.symbol}`);
  };

  if (isLoading) {
    return <div className="p-3 text-sm text-terminal-muted">Loading watchlist...</div>;
  }

  if (isError) {
    return (
      <div className="m-3 flex flex-1 flex-col items-start justify-center gap-3 border border-[#4d2d2d] bg-[#1a1010] p-4 text-sm text-[#ffb5b5]">
        <div className="font-semibold">Watchlist feed unavailable</div>
        <div className="text-xs text-[#e7a7a7]">{error instanceof Error ? error.message : 'Unknown error'}</div>
        <button
          type="button"
          onClick={() => refetch()}
          className="border border-terminal-line bg-[#121b2a] px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-terminal-accent"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data) {
    return <div className="p-3 text-sm text-terminal-muted">No watchlist data available.</div>;
  }

  return (
    <div className="flex h-full flex-col bg-terminal-panel">
      <div className="flex items-center gap-2 border-b border-terminal-line px-2 py-1 text-[11px] uppercase tracking-wide text-terminal-muted">
        <span>WL</span>
        <span className="text-[10px] text-[#6f819c]">{data.items.length} symbols</span>
        <span className="ml-auto text-[10px]">As of {new Date(data.asOf).toLocaleTimeString()}</span>
      </div>

      {data.warnings.length > 0 && (
        <div className="mx-2 mt-2 border border-[#493826] bg-[#20160f] px-2 py-1 text-[11px] text-[#ffcc9a]">
          {data.warnings.join(' | ')}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-auto p-2">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wide text-terminal-muted">
              <th className="px-2 py-1">Symbol</th>
              <th className="px-2 py-1 text-right">Last</th>
              <th className="px-2 py-1 text-right">Chg</th>
              <th className="px-2 py-1 text-right">Vol</th>
              <th className="px-2 py-1 text-right">Alert</th>
              <th className="px-2 py-1 text-right">Act</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-t border-[#152033] bg-[#0b1119]">
              <td colSpan={6} className="px-2 py-1.5">
                <form onSubmit={onAdd} className="flex items-center gap-2">
                  <span className="text-[10px] uppercase tracking-wide text-terminal-muted">WL ADD</span>
                  <input
                    value={symbolInput}
                    onChange={(event) => setSymbolInput(event.target.value)}
                    className="h-6 w-36 border border-[#233044] bg-[#05080d] px-2 text-xs text-[#d7e2f0] outline-none ring-terminal-accent focus:ring-1"
                    spellCheck={false}
                    placeholder="AAPL / EURUSD"
                  />
                  <button
                    type="submit"
                    disabled={busyKey === 'add'}
                    className="h-6 border border-terminal-line bg-[#121b2a] px-2 text-[10px] font-semibold uppercase tracking-wide text-terminal-accent disabled:opacity-60"
                  >
                    {busyKey === 'add' ? 'Adding...' : 'Add'}
                  </button>
                </form>
              </td>
            </tr>

            {data.items.map((item) => {
              const quote = item.quote;
              const change = quote?.change ?? 0;
              const changePercent = quote?.changePercent ?? 0;
              const alertState = summarizeAlertState(item);

              return (
                <tr key={item.id} className={clsx('border-t border-[#152033] hover:bg-[#10192a]', item.alerts.some((a) => a.triggerState === 'triggered') && 'bg-[#1d1c0f]')}>
                  <td className="px-2 py-1 font-semibold text-[#e5eefb]">
                    <button
                      type="button"
                      onClick={() => onOpenIntra(item)}
                      className="inline-flex items-center gap-1 border border-transparent px-0.5 py-0.5 text-left text-inherit hover:border-[#2d3b54] hover:bg-[#0e1521]"
                      title={`Open INTRA ${item.symbol}`}
                    >
                      <span>{item.displaySymbol}</span>
                      <span className="text-[10px] text-terminal-muted">{item.instrumentType.toUpperCase()}</span>
                    </button>
                  </td>
                  <td className="px-2 py-1 text-right text-[#e0ebfa]">{formatValue(quote?.lastPrice)}</td>
                  <td
                    className={clsx(
                      'px-2 py-1 text-right font-semibold',
                      change >= 0 ? 'text-terminal-up' : 'text-terminal-down'
                    )}
                  >
                    {change >= 0 ? '+' : ''}
                    {change.toFixed(2)} ({changePercent >= 0 ? '+' : ''}
                    {changePercent.toFixed(2)}%)
                  </td>
                  <td className="px-2 py-1 text-right text-[#c2d0e5]">{formatValue(quote?.volume)}</td>
                  <td className="px-2 py-1 text-right">
                    <button
                      type="button"
                      onClick={() => onOpenAlerts(item)}
                      className={clsx(
                        'border px-2 py-0.5 text-[10px] uppercase tracking-wide',
                        alertState.className
                      )}
                      title="Open alerts panel for this symbol"
                    >
                      {alertState.label}
                    </button>
                  </td>
                  <td className="px-2 py-1 text-right">
                    <button
                      type="button"
                      disabled={busyKey === `rm-${item.id}`}
                      onClick={() => onRemove(item.id, item.symbol)}
                      className="border border-terminal-line bg-[#121b2a] px-2 py-0.5 text-[10px] uppercase tracking-wide text-terminal-accent disabled:opacity-60"
                    >
                      {busyKey === `rm-${item.id}` ? '...' : 'RM'}
                    </button>
                  </td>
                </tr>
              );
            })}

            {data.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-2 py-4">
                  <div className="flex flex-col gap-2 border border-terminal-line bg-[#0b1119] p-3 text-[11px] text-terminal-muted">
                    <div className="font-semibold text-[#d3deee]">Watchlist is empty.</div>
                    <div>Add symbols inline above or via command bar: WL ADD AAPL / WL ADD EURUSD.</div>
                    <div>Tip: click any symbol row to quick-open INTRA or ALRT.</div>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
