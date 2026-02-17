'use client';

import { FormEvent, useState } from 'react';
import clsx from 'clsx';
import { useQueryClient } from '@tanstack/react-query';

import { addWatchlistSymbol, removeWatchlistItem } from '@/lib/api';
import { normalizeSymbolToken } from '@/lib/modules';
import { useWatchlist } from '@/hooks/useWatchlist';
import { useTerminalStore } from '@/store/useTerminalStore';

function formatValue(value: number | undefined): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--';
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

export function WatchlistPanel() {
  const [symbolInput, setSymbolInput] = useState('AAPL');
  const [busyItemId, setBusyItemId] = useState<number | null>(null);
  const [isAdding, setIsAdding] = useState(false);

  const queryClient = useQueryClient();
  const setCommandFeedback = useTerminalStore((state) => state.setCommandFeedback);

  const { data, isLoading, isError, error } = useWatchlist();

  const onAdd = async (event: FormEvent) => {
    event.preventDefault();
    const symbol = normalizeSymbolToken(symbolInput);
    if (!symbol) {
      setCommandFeedback('WL ADD requires a symbol.');
      return;
    }

    setIsAdding(true);
    try {
      await addWatchlistSymbol(symbol);
      setCommandFeedback(`Added ${symbol} to watchlist`);
      setSymbolInput(symbol);
      await queryClient.invalidateQueries({ queryKey: ['watchlist'] });
    } catch (requestError) {
      setCommandFeedback(requestError instanceof Error ? requestError.message : 'Failed to add watchlist symbol');
    } finally {
      setIsAdding(false);
    }
  };

  const onRemove = async (itemId: number, symbol: string) => {
    setBusyItemId(itemId);
    try {
      await removeWatchlistItem(itemId);
      setCommandFeedback(`Removed ${symbol} from watchlist`);
      await queryClient.invalidateQueries({ queryKey: ['watchlist'] });
    } catch (requestError) {
      setCommandFeedback(requestError instanceof Error ? requestError.message : 'Failed to remove watchlist symbol');
    } finally {
      setBusyItemId(null);
    }
  };

  return (
    <div className="flex h-full flex-col bg-terminal-panel">
      <form onSubmit={onAdd} className="flex items-center gap-2 border-b border-terminal-line px-2 py-1">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-terminal-muted">WL ADD</span>
        <input
          value={symbolInput}
          onChange={(event) => setSymbolInput(event.target.value)}
          className="h-7 w-36 border border-[#233044] bg-[#05080d] px-2 text-sm text-[#d7e2f0] outline-none ring-terminal-accent focus:ring-1"
          spellCheck={false}
        />
        <button
          type="submit"
          disabled={isAdding}
          className="h-7 border border-terminal-line bg-[#121b2a] px-2 text-[11px] font-semibold uppercase tracking-wide text-terminal-accent disabled:opacity-60"
        >
          {isAdding ? 'Adding...' : 'Add'}
        </button>

        <div className="ml-auto text-[11px] text-terminal-muted">
          {data ? `${data.items.length} symbols` : 'No symbols loaded'}
        </div>
      </form>

      {isLoading && <div className="p-3 text-sm text-terminal-muted">Loading watchlist...</div>}

      {isError && (
        <div className="p-3 text-sm text-terminal-down">
          Failed to load watchlist: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      )}

      {!isLoading && !isError && data && (
        <>
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
                  <th className="px-2 py-1 text-right">Act</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => {
                  const quote = item.quote;
                  const change = quote?.change ?? 0;
                  const changePercent = quote?.changePercent ?? 0;

                  return (
                    <tr key={item.id} className="border-t border-[#152033]">
                      <td className="px-2 py-1 font-semibold text-[#e5eefb]">
                        {item.displaySymbol}
                        <span className="ml-1 text-[10px] text-terminal-muted">{item.instrumentType.toUpperCase()}</span>
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
                          disabled={busyItemId === item.id}
                          onClick={() => onRemove(item.id, item.symbol)}
                          className="border border-terminal-line bg-[#121b2a] px-2 py-0.5 text-[10px] uppercase tracking-wide text-terminal-accent disabled:opacity-60"
                        >
                          {busyItemId === item.id ? '...' : 'RM'}
                        </button>
                      </td>
                    </tr>
                  );
                })}

                {data.items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-2 py-3 text-terminal-muted">
                      Watchlist is empty. Add symbols with WL ADD &lt;symbol&gt;.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="border-t border-terminal-line px-2 py-1 text-[10px] uppercase tracking-wide text-terminal-muted">
            {data.items.length > 0 ? `Updated ${new Date(data.asOf).toLocaleTimeString()}` : 'WL READY'}
          </div>
        </>
      )}
    </div>
  );
}
