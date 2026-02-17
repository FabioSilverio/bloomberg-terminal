'use client';

import React, { FormEvent, useEffect, useMemo, useState } from 'react';
import clsx from 'clsx';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import {
  AlertCondition,
  PriceAlert,
  createPriceAlert,
  fetchPriceAlerts,
  fetchWatchlist,
  removePriceAlert,
  updatePriceAlert
} from '@/lib/api';
import { normalizeSymbolToken } from '@/lib/modules';
import { useTerminalStore } from '@/store/useTerminalStore';

interface AlertsPanelProps {
  panelId: string;
  initialSymbol?: string;
}

const CONDITION_OPTIONS: Array<{ value: AlertCondition; label: string; short: string }> = [
  { value: 'price_above', label: 'Price Above', short: 'ABOVE' },
  { value: 'price_below', label: 'Price Below', short: 'BELOW' },
  { value: 'crosses_above', label: 'Crosses Above', short: 'XABOVE' },
  { value: 'crosses_below', label: 'Crosses Below', short: 'XBELOW' },
  { value: 'percent_move_up', label: '% Move Up', short: 'PCTUP' },
  { value: 'percent_move_down', label: '% Move Down', short: 'PCTDOWN' }
];

function formatCondition(condition: AlertCondition): string {
  return CONDITION_OPTIONS.find((entry) => entry.value === condition)?.short ?? condition;
}

function formatNumber(value: number | undefined): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--';
  }

  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function formatDateTime(value?: string): string {
  if (!value) {
    return '--';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '--';
  }

  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
}

export function AlertsPanel({ panelId, initialSymbol }: AlertsPanelProps) {
  const normalizedInitialSymbol = normalizeSymbolToken(initialSymbol ?? 'AAPL') || 'AAPL';

  const [symbolInput, setSymbolInput] = useState(normalizedInitialSymbol);
  const [condition, setCondition] = useState<AlertCondition>('price_above');
  const [thresholdInput, setThresholdInput] = useState('200');
  const [enabled, setEnabled] = useState(true);
  const [oneShot, setOneShot] = useState(false);
  const [cooldownInput, setCooldownInput] = useState('60');
  const [editingAlertId, setEditingAlertId] = useState<number | null>(null);
  const [filterStatus, setFilterStatus] = useState<'all' | 'active' | 'inactive'>('all');
  const [filterSymbolInput, setFilterSymbolInput] = useState('');
  const [busyId, setBusyId] = useState<number | 'submit' | null>(null);

  const queryClient = useQueryClient();

  const setPanelContext = useTerminalStore((state) => state.setPanelContext);
  const setCommandFeedback = useTerminalStore((state) => state.setCommandFeedback);
  const alertSoundEnabled = useTerminalStore((state) => state.alertSoundEnabled);
  const setAlertSoundEnabled = useTerminalStore((state) => state.setAlertSoundEnabled);

  const normalizedFilterSymbol = normalizeSymbolToken(filterSymbolInput);

  const alertsQuery = useQuery({
    queryKey: ['alerts', normalizedFilterSymbol, filterStatus],
    queryFn: () =>
      fetchPriceAlerts({
        symbol: normalizedFilterSymbol || undefined,
        status: filterStatus === 'all' ? undefined : filterStatus
      }),
    refetchInterval: 2000
  });

  const watchlistQuery = useQuery({
    queryKey: ['watchlist'],
    queryFn: fetchWatchlist,
    refetchInterval: 4000
  });

  const watchlistSymbols = useMemo(
    () => (watchlistQuery.data?.items ?? []).map((item) => item.symbol),
    [watchlistQuery.data?.items]
  );

  useEffect(() => {
    if (!initialSymbol) {
      return;
    }

    const normalized = normalizeSymbolToken(initialSymbol);
    if (!normalized) {
      return;
    }

    setSymbolInput(normalized);
    setPanelContext(panelId, { symbol: normalized });
  }, [initialSymbol, panelId, setPanelContext]);

  const resetForm = () => {
    setEditingAlertId(null);
    setCondition('price_above');
    setThresholdInput('200');
    setEnabled(true);
    setOneShot(false);
    setCooldownInput('60');
  };

  const hydrateForm = (alert: PriceAlert) => {
    setEditingAlertId(alert.id);
    setSymbolInput(alert.symbol);
    setCondition(alert.condition);
    setThresholdInput(String(alert.threshold));
    setEnabled(alert.enabled);
    setOneShot(alert.oneShot);
    setCooldownInput(String(alert.cooldownSeconds));
  };

  const refreshData = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['alerts'] }),
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
    ]);
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();

    const symbol = normalizeSymbolToken(symbolInput);
    const threshold = Number(thresholdInput);
    const cooldownSeconds = Number(cooldownInput);

    if (!symbol) {
      setCommandFeedback('ALRT ADD requires a symbol (examples: AAPL, EURUSD, GBP/JPY).');
      return;
    }

    if (!Number.isFinite(threshold) || threshold <= 0) {
      setCommandFeedback('Alert threshold must be a number greater than zero.');
      return;
    }

    if (!Number.isFinite(cooldownSeconds) || cooldownSeconds < 0) {
      setCommandFeedback('Cooldown must be >= 0 seconds.');
      return;
    }

    setBusyId('submit');
    try {
      if (editingAlertId) {
        await updatePriceAlert(editingAlertId, {
          symbol,
          condition,
          threshold,
          enabled,
          oneShot,
          cooldownSeconds
        });
        setCommandFeedback(`Updated alert #${editingAlertId} (${symbol})`);
      } else {
        await createPriceAlert({
          symbol,
          condition,
          threshold,
          enabled,
          oneShot,
          cooldownSeconds,
          source: watchlistSymbols.includes(symbol) ? 'watchlist' : 'manual'
        });
        setCommandFeedback(`Created alert for ${symbol}: ${formatCondition(condition)} ${threshold}`);
      }

      setPanelContext(panelId, { symbol });
      await refreshData();
      resetForm();
    } catch (error) {
      setCommandFeedback(error instanceof Error ? error.message : 'Failed to save alert');
    } finally {
      setBusyId(null);
    }
  };

  const onDelete = async (alert: PriceAlert) => {
    setBusyId(alert.id);
    try {
      await removePriceAlert(alert.id);
      await refreshData();
      if (editingAlertId === alert.id) {
        resetForm();
      }
      setCommandFeedback(`Removed alert #${alert.id}`);
    } catch (error) {
      setCommandFeedback(error instanceof Error ? error.message : 'Failed to remove alert');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="flex h-full flex-col bg-terminal-panel">
      <div className="flex items-center gap-2 border-b border-terminal-line px-2 py-1 text-[11px] uppercase tracking-wide text-terminal-muted">
        <span>ALRT</span>
        <span className="text-[10px] text-[#6f819c]">{alertsQuery.data?.items.length ?? 0} alerts</span>
        <button
          type="button"
          onClick={() => setAlertSoundEnabled(!alertSoundEnabled)}
          className={clsx(
            'ml-auto border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
            alertSoundEnabled
              ? 'border-[#3f6e4f] bg-[#112419] text-[#8de8b2]'
              : 'border-[#4c3940] bg-[#1d1417] text-[#f4b6c4]'
          )}
          title="Global alert sound toggle"
        >
          Sound {alertSoundEnabled ? 'ON' : 'OFF'}
        </button>
      </div>

      <form onSubmit={onSubmit} className="grid grid-cols-6 gap-2 border-b border-terminal-line px-2 py-2 text-xs">
        <label className="col-span-2 flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wide text-terminal-muted">Symbol</span>
          <input
            value={symbolInput}
            onChange={(event) => setSymbolInput(event.target.value)}
            className="h-7 border border-[#233044] bg-[#05080d] px-2 text-xs text-[#d7e2f0] outline-none ring-terminal-accent focus:ring-1"
            placeholder="AAPL / EURUSD"
            spellCheck={false}
          />
        </label>

        <label className="col-span-2 flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wide text-terminal-muted">Condition</span>
          <select
            value={condition}
            onChange={(event) => setCondition(event.target.value as AlertCondition)}
            className="h-7 border border-[#233044] bg-[#05080d] px-2 text-xs text-[#d7e2f0] outline-none"
          >
            {CONDITION_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="col-span-1 flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wide text-terminal-muted">Value</span>
          <input
            value={thresholdInput}
            onChange={(event) => setThresholdInput(event.target.value)}
            className="h-7 border border-[#233044] bg-[#05080d] px-2 text-xs text-[#d7e2f0] outline-none ring-terminal-accent focus:ring-1"
            inputMode="decimal"
          />
        </label>

        <label className="col-span-1 flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wide text-terminal-muted">Cooldown</span>
          <input
            value={cooldownInput}
            onChange={(event) => setCooldownInput(event.target.value)}
            className="h-7 border border-[#233044] bg-[#05080d] px-2 text-xs text-[#d7e2f0] outline-none ring-terminal-accent focus:ring-1"
            inputMode="numeric"
          />
        </label>

        <label className="col-span-1 flex items-center gap-2 text-[10px] uppercase tracking-wide text-terminal-muted">
          <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /> Enabled
        </label>
        <label className="col-span-1 flex items-center gap-2 text-[10px] uppercase tracking-wide text-terminal-muted">
          <input type="checkbox" checked={oneShot} onChange={(event) => setOneShot(event.target.checked)} /> One-shot
        </label>

        <div className="col-span-4 flex items-end gap-2 text-[10px] uppercase tracking-wide text-terminal-muted">
          <span>Command:</span>
          <span className="text-[#8ea0b8]">
            ALRT ADD {normalizeSymbolToken(symbolInput) || '<symbol>'} {formatCondition(condition)} {thresholdInput || '0'}
          </span>
        </div>

        <div className="col-span-2 flex items-end justify-end gap-2">
          <button
            type="button"
            onClick={resetForm}
            className="h-7 border border-terminal-line bg-[#121b2a] px-2 text-[10px] font-semibold uppercase tracking-wide text-terminal-accent"
          >
            Clear
          </button>
          <button
            type="submit"
            disabled={busyId === 'submit'}
            className="h-7 border border-terminal-line bg-[#121b2a] px-2 text-[10px] font-semibold uppercase tracking-wide text-terminal-accent disabled:opacity-60"
          >
            {busyId === 'submit' ? 'Saving...' : editingAlertId ? `Save #${editingAlertId}` : 'Create Alert'}
          </button>
        </div>
      </form>

      <div className="flex items-center gap-2 border-b border-terminal-line px-2 py-1 text-[10px] uppercase tracking-wide text-terminal-muted">
        <span>Filter</span>
        <input
          value={filterSymbolInput}
          onChange={(event) => setFilterSymbolInput(event.target.value)}
          className="h-6 w-32 border border-[#233044] bg-[#05080d] px-2 text-[10px] text-[#d7e2f0] outline-none ring-terminal-accent focus:ring-1"
          placeholder="symbol"
          spellCheck={false}
        />
        <select
          value={filterStatus}
          onChange={(event) => setFilterStatus(event.target.value as 'all' | 'active' | 'inactive')}
          className="h-6 border border-[#233044] bg-[#05080d] px-2 text-[10px] text-[#d7e2f0] outline-none"
        >
          <option value="all">All</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-2">
        {alertsQuery.isLoading && <div className="text-xs text-terminal-muted">Loading alerts...</div>}

        {alertsQuery.isError && (
          <div className="border border-[#4d2d2d] bg-[#1a1010] p-3 text-xs text-[#ffb5b5]">
            {alertsQuery.error instanceof Error ? alertsQuery.error.message : 'Failed to load alerts'}
          </div>
        )}

        {!alertsQuery.isLoading && !alertsQuery.isError && (
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wide text-terminal-muted">
                <th className="px-2 py-1">ID</th>
                <th className="px-2 py-1">Symbol</th>
                <th className="px-2 py-1">Condition</th>
                <th className="px-2 py-1 text-right">Value</th>
                <th className="px-2 py-1">State</th>
                <th className="px-2 py-1">Last Trigger</th>
                <th className="px-2 py-1">Source</th>
                <th className="px-2 py-1 text-right">Act</th>
              </tr>
            </thead>
            <tbody>
              {(alertsQuery.data?.items ?? []).map((alert) => (
                <tr
                  key={alert.id}
                  className={clsx(
                    'border-t border-[#152033] hover:bg-[#10192a]',
                    alert.triggerState === 'triggered' && 'bg-[#1d1c0f]',
                    editingAlertId === alert.id && 'bg-[#0f1724]'
                  )}
                >
                  <td className="px-2 py-1 font-semibold text-[#d8e4f5]">#{alert.id}</td>
                  <td className="px-2 py-1">
                    <button
                      type="button"
                      onClick={() => hydrateForm(alert)}
                      className="border border-transparent px-1 py-0.5 text-left text-[#e5eefb] hover:border-[#2d3b54] hover:bg-[#0e1521]"
                    >
                      {alert.symbol}
                    </button>
                  </td>
                  <td className="px-2 py-1 text-[#c6d6ea]">{formatCondition(alert.condition)}</td>
                  <td className="px-2 py-1 text-right text-[#e5eefb]">{formatNumber(alert.threshold)}</td>
                  <td className="px-2 py-1">
                    <span
                      className={clsx(
                        'inline-flex border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
                        alert.triggerState === 'triggered' && 'border-[#8f7c2d] bg-[#2a2410] text-[#ffdf7a]',
                        alert.triggerState === 'active' && 'border-[#3f6e4f] bg-[#112419] text-[#8de8b2]',
                        alert.triggerState === 'cooldown' && 'border-[#706340] bg-[#221e10] text-[#ffd48a]',
                        alert.triggerState === 'inactive' && 'border-[#4c3940] bg-[#1d1417] text-[#f4b6c4]',
                        alert.triggerState === 'armed' && 'border-terminal-line bg-[#121b2a] text-terminal-accent'
                      )}
                    >
                      {alert.triggerState}
                    </span>
                  </td>
                  <td className="px-2 py-1 text-[11px] text-[#b8c9df]">{formatDateTime(alert.lastTriggeredAt)}</td>
                  <td className="px-2 py-1 text-[11px] text-[#9fb3ce]">{alert.lastTriggerSource ?? alert.source}</td>
                  <td className="px-2 py-1 text-right">
                    <button
                      type="button"
                      onClick={() => onDelete(alert)}
                      disabled={busyId === alert.id}
                      className="border border-terminal-line bg-[#121b2a] px-2 py-0.5 text-[10px] uppercase tracking-wide text-terminal-accent disabled:opacity-60"
                    >
                      {busyId === alert.id ? '...' : 'RM'}
                    </button>
                  </td>
                </tr>
              ))}

              {(alertsQuery.data?.items.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={8} className="px-2 py-4">
                    <div className="border border-terminal-line bg-[#0b1119] p-3 text-[11px] text-terminal-muted">
                      No alerts yet. Add one above or via command: ALRT ADD AAPL ABOVE 200.
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
