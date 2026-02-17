'use client';

import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import clsx from 'clsx';
import {
  ColorType,
  IChartApi,
  ISeriesApi,
  LineData,
  UTCTimestamp,
  createChart
} from 'lightweight-charts';

import { useIntraday } from '@/hooks/useIntraday';
import { IntradayPoint } from '@/lib/api';
import { normalizeSymbolToken } from '@/lib/modules';
import { useTerminalStore } from '@/store/useTerminalStore';

interface IntradayPanelProps {
  panelId: string;
  initialSymbol: string;
}

function formatNumber(value: number | undefined): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--';
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function IntradayChart({ points }: { points: IntradayPoint[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 280,
      layout: {
        textColor: '#b8c7db',
        background: { type: ColorType.Solid, color: '#09111b' }
      },
      grid: {
        vertLines: { color: '#1a2434' },
        horzLines: { color: '#1a2434' }
      },
      timeScale: {
        borderColor: '#263347',
        timeVisible: true,
        secondsVisible: false
      },
      rightPriceScale: {
        borderColor: '#263347'
      },
      crosshair: {
        vertLine: { color: '#415976' },
        horzLine: { color: '#415976' }
      }
    });

    const series = chart.addLineSeries({
      color: '#ff9a2f',
      lineWidth: 2,
      priceLineVisible: false
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const observer = new ResizeObserver(() => {
      if (!containerRef.current || !chartRef.current) {
        return;
      }

      chartRef.current.applyOptions({
        width: containerRef.current.clientWidth,
        height: Math.max(220, containerRef.current.clientHeight)
      });
    });

    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current) {
      return;
    }

    const data: LineData[] = points
      .map((point) => ({
        time: Math.floor(new Date(point.time).getTime() / 1000) as UTCTimestamp,
        value: point.price
      }))
      .filter((point) => Number.isFinite(point.time) && Number.isFinite(point.value));

    seriesRef.current.setData(data);

    if (data.length > 1) {
      chartRef.current?.timeScale().fitContent();
    }
  }, [points]);

  return <div ref={containerRef} className="h-[280px] w-full border border-terminal-line bg-[#09111b]" />;
}

export function IntradayPanel({ panelId, initialSymbol }: IntradayPanelProps) {
  const normalizedInitial = normalizeSymbolToken(initialSymbol) || 'AAPL';
  const [symbolInput, setSymbolInput] = useState(normalizedInitial);
  const [activeSymbol, setActiveSymbol] = useState(normalizedInitial);

  const setPanelContext = useTerminalStore((state) => state.setPanelContext);
  const setCommandFeedback = useTerminalStore((state) => state.setCommandFeedback);

  const { data, isLoading, isError, error } = useIntraday(activeSymbol);

  useEffect(() => {
    const normalized = normalizeSymbolToken(initialSymbol) || 'AAPL';
    setSymbolInput(normalized);
    setActiveSymbol(normalized);
  }, [initialSymbol]);

  const onSubmitSymbol = (event: FormEvent) => {
    event.preventDefault();

    const normalized = normalizeSymbolToken(symbolInput);
    if (!normalized) {
      setCommandFeedback('Enter a valid symbol (examples: AAPL, EURUSD, BTC-USD).');
      return;
    }

    setActiveSymbol(normalized);
    setPanelContext(panelId, { symbol: normalized });
    setCommandFeedback(`INTRA ${normalized}`);
  };

  const points = useMemo(() => data?.points ?? [], [data?.points]);
  const lastTick = points.length > 0 ? points[points.length - 1] : undefined;

  const latestRows = useMemo(() => {
    if (points.length <= 6) {
      return [...points].reverse();
    }
    return points.slice(-6).reverse();
  }, [points]);

  return (
    <div className="flex h-full flex-col bg-terminal-panel">
      <form onSubmit={onSubmitSymbol} className="flex items-center gap-2 border-b border-terminal-line px-2 py-1">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-terminal-muted">Symbol</span>
        <input
          value={symbolInput}
          onChange={(event) => setSymbolInput(event.target.value)}
          className="h-7 w-36 border border-[#233044] bg-[#05080d] px-2 text-sm text-[#d7e2f0] outline-none ring-terminal-accent focus:ring-1"
          spellCheck={false}
        />
        <button
          type="submit"
          className="h-7 border border-terminal-line bg-[#121b2a] px-2 text-[11px] font-semibold uppercase tracking-wide text-terminal-accent"
        >
          Load
        </button>

        <div className="ml-auto text-[11px] text-terminal-muted">
          {data ? `As of ${new Date(data.asOf).toLocaleTimeString()}` : 'Waiting for data...'}
        </div>
      </form>

      {isLoading && <div className="p-3 text-sm text-terminal-muted">Loading intraday feed...</div>}

      {isError && (
        <div className="p-3 text-sm text-terminal-down">
          Failed to load intraday data: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      )}

      {!isLoading && !isError && data && (
        <>
          <div className="grid grid-cols-2 gap-2 border-b border-terminal-line px-2 py-2 text-xs md:grid-cols-4">
            <div>
              <div className="text-[10px] uppercase tracking-wide text-terminal-muted">Last</div>
              <div className="text-sm font-semibold text-[#e4eefc]">{formatNumber(data.lastPrice)}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wide text-terminal-muted">Change</div>
              <div className={clsx('text-sm font-semibold', data.change >= 0 ? 'text-terminal-up' : 'text-terminal-down')}>
                {data.change >= 0 ? '+' : ''}
                {data.change.toFixed(2)} ({data.changePercent >= 0 ? '+' : ''}
                {data.changePercent.toFixed(2)}%)
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wide text-terminal-muted">Volume</div>
              <div className="text-sm font-semibold text-[#e4eefc]">{formatNumber(data.volume)}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wide text-terminal-muted">Source</div>
              <div className="text-sm font-semibold text-[#d9e5f7]">{data.source}</div>
            </div>
          </div>

          <div className="p-2">
            <IntradayChart points={points} />
          </div>

          {data.warnings.length > 0 && (
            <div className="mx-2 mb-2 border border-[#493826] bg-[#20160f] px-2 py-1 text-[11px] text-[#ffcc9a]">
              {data.warnings.join(' | ')}
            </div>
          )}

          <div className="min-h-0 flex-1 overflow-auto px-2 pb-2">
            <table className="w-full border-collapse text-xs">
              <thead>
                <tr className="text-left text-[10px] uppercase tracking-wide text-terminal-muted">
                  <th className="px-2 py-1">Time</th>
                  <th className="px-2 py-1 text-right">Price</th>
                  <th className="px-2 py-1 text-right">Volume</th>
                </tr>
              </thead>
              <tbody>
                {latestRows.map((row) => (
                  <tr key={`${row.time}-${row.price}`} className="border-t border-[#152033]">
                    <td className="px-2 py-1 text-[#b2c2d9]">{new Date(row.time).toLocaleTimeString()}</td>
                    <td className="px-2 py-1 text-right font-semibold text-[#e5eefb]">{formatNumber(row.price)}</td>
                    <td className="px-2 py-1 text-right text-[#c8d4e6]">{formatNumber(row.volume)}</td>
                  </tr>
                ))}

                {latestRows.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-2 py-3 text-terminal-muted">
                      No intraday points available yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

            {lastTick && (
              <div className="mt-2 text-[10px] uppercase tracking-wide text-terminal-muted">
                Last tick {new Date(lastTick.time).toLocaleTimeString()} · {data.displaySymbol} ·{' '}
                {data.stale ? 'STALE' : 'LIVE'}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
