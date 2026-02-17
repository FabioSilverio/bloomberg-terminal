'use client';

import React, { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import clsx from 'clsx';
import { useQuery } from '@tanstack/react-query';
import { ColorType, IChartApi, ISeriesApi, LineData, UTCTimestamp, createChart } from 'lightweight-charts';

import { useIntraday } from '@/hooks/useIntraday';
import { IntradayPoint, fetchPriceAlerts } from '@/lib/api';
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

function toLineSeriesData(points: IntradayPoint[]): LineData[] {
  const byTime = new Map<number, number>();

  for (const point of points) {
    const time = Math.floor(new Date(point.time).getTime() / 1000);
    if (!Number.isFinite(time) || !Number.isFinite(point.price)) {
      continue;
    }

    byTime.set(time, point.price);
  }

  return [...byTime.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([time, value]) => ({
      time: time as UTCTimestamp,
      value
    }));
}

function IntradayChart({ points }: { points: IntradayPoint[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const [chartError, setChartError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    let chart: IChartApi | null = null;
    let observer: ResizeObserver | null = null;

    try {
      chart = createChart(containerRef.current, {
        width: containerRef.current.clientWidth,
        height: 250,
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
      setChartError(null);

      observer = new ResizeObserver(() => {
        if (!containerRef.current || !chartRef.current) {
          return;
        }

        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
          height: Math.max(190, containerRef.current.clientHeight)
        });
      });

      observer.observe(containerRef.current);
    } catch (error) {
      setChartError(error instanceof Error ? error.message : 'Chart initialization error');
    }

    return () => {
      observer?.disconnect();
      chart?.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current) {
      return;
    }

    const data = toLineSeriesData(points);

    try {
      seriesRef.current.setData(data);
      if (data.length > 1) {
        chartRef.current?.timeScale().fitContent();
      }
      setChartError(null);
    } catch (error) {
      setChartError(error instanceof Error ? error.message : 'Chart update error');
    }
  }, [points]);

  return (
    <div className="space-y-1">
      {chartError && <div className="text-[10px] text-terminal-down">Chart fallback active: {chartError}</div>}
      <div ref={containerRef} className="h-[250px] w-full border border-terminal-line bg-[#09111b]" />
    </div>
  );
}

export function IntradayPanel({ panelId, initialSymbol }: IntradayPanelProps) {
  const normalizedInitial = normalizeSymbolToken(initialSymbol) || 'AAPL';
  const [symbolInput, setSymbolInput] = useState(normalizedInitial);
  const [activeSymbol, setActiveSymbol] = useState(normalizedInitial);
  const [loadingSince, setLoadingSince] = useState<number | null>(null);

  const setPanelContext = useTerminalStore((state) => state.setPanelContext);
  const setCommandFeedback = useTerminalStore((state) => state.setCommandFeedback);

  const { data, isLoading, isError, error, streamStatus } = useIntraday(activeSymbol);
  const alertsQuery = useQuery({
    queryKey: ['alerts', activeSymbol, 'active'],
    queryFn: () => fetchPriceAlerts({ symbol: activeSymbol, status: 'active' }),
    refetchInterval: 2000
  });

  useEffect(() => {
    const normalized = normalizeSymbolToken(initialSymbol) || 'AAPL';
    setSymbolInput(normalized);
    setActiveSymbol(normalized);
  }, [initialSymbol]);

  useEffect(() => {
    if (isLoading) {
      setLoadingSince((current) => current ?? Date.now());
      return;
    }

    setLoadingSince(null);
  }, [isLoading]);

  const onSubmitSymbol = (event: FormEvent) => {
    event.preventDefault();

    const normalized = normalizeSymbolToken(symbolInput);
    if (!normalized) {
      setCommandFeedback('Enter a valid symbol (examples: AAPL, EURUSD, EURUSD Curncy, BTC-USD).');
      return;
    }

    setActiveSymbol(normalized);
    setPanelContext(panelId, { symbol: normalized });
    setCommandFeedback(`INTRA ${normalized}`);
  };

  const points = useMemo(() => data?.points ?? [], [data?.points]);
  const symbolAlerts = alertsQuery.data?.items ?? [];
  const triggeredAlerts = symbolAlerts.filter((alert) => alert.triggerState === 'triggered');
  const lastTick = points.length > 0 ? points[points.length - 1] : undefined;

  const latestRows = useMemo(() => {
    if (points.length <= 6) {
      return [...points].reverse();
    }
    return points.slice(-6).reverse();
  }, [points]);

  const loadingTooLong = loadingSince !== null && Date.now() - loadingSince > 7000;

  return (
    <div className="flex h-full flex-col bg-terminal-panel">
      <form onSubmit={onSubmitSymbol} className="flex items-center gap-2 border-b border-terminal-line px-2 py-1">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-terminal-muted">Symbol</span>
        <input
          value={symbolInput}
          onChange={(event) => setSymbolInput(event.target.value)}
          className="h-6 w-40 border border-[#233044] bg-[#05080d] px-2 text-xs text-[#d7e2f0] outline-none ring-terminal-accent focus:ring-1"
          spellCheck={false}
        />
        <button
          type="submit"
          className="h-6 border border-terminal-line bg-[#121b2a] px-2 text-[10px] font-semibold uppercase tracking-wide text-terminal-accent"
        >
          Load
        </button>

        <span className="text-[10px] text-terminal-muted">Examples: USD/BRL, USDBRL, BRLUSD, AAPL, BTCUSD</span>

        <div className="ml-auto flex items-center gap-2 text-[10px] uppercase tracking-wide">
          <span className="text-terminal-muted">{data ? `As of ${new Date(data.asOf).toLocaleTimeString()}` : 'Waiting...'}</span>
          {triggeredAlerts.length > 0 ? (
            <span className="rounded-sm border border-[#8f7c2d] bg-[#2a2410] px-1 py-0.5 text-[#ffdf7a]">
              Alert Triggered ({triggeredAlerts.length})
            </span>
          ) : symbolAlerts.length > 0 ? (
            <span className="rounded-sm border border-[#3f6e4f] bg-[#112419] px-1 py-0.5 text-[#8de8b2]">
              Alerts Armed ({symbolAlerts.length})
            </span>
          ) : null}
          <span
            className={clsx(
              'rounded-sm border px-1 py-0.5',
              streamStatus === 'live'
                ? 'border-[#2f5f45] bg-[#0f2319] text-[#84e9b0]'
                : streamStatus === 'connecting'
                  ? 'border-[#60563a] bg-[#201b12] text-[#e9cd84]'
                  : 'border-[#2b3a53] bg-[#101725] text-[#9eb8de]'
            )}
          >
            {streamStatus}
          </span>
        </div>
      </form>

      {triggeredAlerts.length > 0 && (
        <div className="mx-2 mt-2 border border-[#8f7c2d] bg-[#2a2410] px-2 py-1 text-[11px] text-[#ffdf7a]">
          Triggered alerts: {triggeredAlerts.map((alert) => `#${alert.id} ${alert.condition} ${formatNumber(alert.threshold)}`).join(' | ')}
        </div>
      )}

      {isLoading && (
        <div className="space-y-1 p-3 text-sm text-terminal-muted">
          <div>Loading intraday feed...</div>
          {loadingTooLong && <div className="text-[11px] text-[#d5b98a]">Still loading. If this persists, try another symbol.</div>}
        </div>
      )}

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
                      No intraday points yet. Try another symbol or wait for the next tick.
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
