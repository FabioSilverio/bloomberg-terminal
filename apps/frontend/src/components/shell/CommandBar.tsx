'use client';

import { FormEvent, KeyboardEvent, RefObject, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { addWatchlistSymbol, createPriceAlert, removePriceAlert, removeWatchlistSymbol } from '@/lib/api';
import { CommandContext, ModuleCode, parseCommand } from '@/lib/modules';

interface CommandBarProps {
  inputRef: RefObject<HTMLInputElement | null>;
  onOpenModule: (module: ModuleCode, context?: CommandContext) => void;
  onSetMmapRefresh: (refreshMs: number) => void;
  onFeedback: (message: string) => void;
}

export function CommandBar({ inputRef, onOpenModule, onSetMmapRefresh, onFeedback }: CommandBarProps) {
  const [value, setValue] = useState('MMAP');
  const [busy, setBusy] = useState(false);
  const queryClient = useQueryClient();

  const historyRef = useRef<string[]>(['MMAP']);
  const historyIndexRef = useRef<number>(-1);

  const pushHistory = (entry: string) => {
    const normalized = entry.trim();
    if (!normalized) {
      return;
    }

    if (historyRef.current[0] !== normalized) {
      historyRef.current = [normalized, ...historyRef.current].slice(0, 40);
    }

    historyIndexRef.current = -1;
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();

    if (busy) {
      return;
    }

    const command = parseCommand(value);

    if (command.type === 'open-module') {
      onOpenModule(command.module, command.context);
      pushHistory(value);
      if (command.module === 'INTRA' && command.context?.symbol) {
        setValue(`INTRA ${command.context.symbol}`);
      } else {
        setValue(command.module);
      }
      return;
    }

    if (command.type === 'set-mmap-refresh') {
      onSetMmapRefresh(command.intervalMs);
      onFeedback(`MMAP refresh interval set to ${(command.intervalMs / 1000).toFixed(1)}s`);
      pushHistory(value);
      setValue(`MMAP REFRESH ${Math.round(command.intervalMs / 1000)}S`);
      return;
    }

    if (command.type === 'watchlist-add') {
      setBusy(true);
      try {
        await addWatchlistSymbol(command.symbol);
        await queryClient.invalidateQueries({ queryKey: ['watchlist'] });
        onOpenModule('WL');
        onFeedback(`Added ${command.symbol} to watchlist`);
        pushHistory(value);
        setValue(`WL ADD ${command.symbol}`);
      } catch (error) {
        onFeedback(error instanceof Error ? error.message : 'Failed to add watchlist symbol');
      } finally {
        setBusy(false);
      }
      return;
    }

    if (command.type === 'watchlist-remove') {
      setBusy(true);
      try {
        await removeWatchlistSymbol(command.symbol);
        await queryClient.invalidateQueries({ queryKey: ['watchlist'] });
        onFeedback(`Removed ${command.symbol} from watchlist`);
        pushHistory(value);
        setValue(`WL RM ${command.symbol}`);
      } catch (error) {
        onFeedback(error instanceof Error ? error.message : 'Failed to remove watchlist symbol');
      } finally {
        setBusy(false);
      }
      return;
    }

    if (command.type === 'alert-add') {
      setBusy(true);
      try {
        await createPriceAlert({
          symbol: command.symbol,
          condition: command.condition,
          threshold: command.threshold,
          enabled: true,
          source: 'command'
        });
        await queryClient.invalidateQueries({ queryKey: ['alerts'] });
        await queryClient.invalidateQueries({ queryKey: ['watchlist'] });
        onOpenModule('ALRT', { symbol: command.symbol });
        onFeedback(`Alert added: ${command.symbol} ${command.condition} ${command.threshold}`);
        pushHistory(value);
        setValue(`ALRT ADD ${command.symbol} ${command.condition.toUpperCase()} ${command.threshold}`);
      } catch (error) {
        onFeedback(error instanceof Error ? error.message : 'Failed to add alert');
      } finally {
        setBusy(false);
      }
      return;
    }

    if (command.type === 'alert-remove') {
      setBusy(true);
      try {
        await removePriceAlert(command.alertId);
        await queryClient.invalidateQueries({ queryKey: ['alerts'] });
        await queryClient.invalidateQueries({ queryKey: ['watchlist'] });
        onFeedback(`Alert #${command.alertId} removed`);
        pushHistory(value);
        setValue(`ALRT RM ${command.alertId}`);
      } catch (error) {
        onFeedback(error instanceof Error ? error.message : 'Failed to remove alert');
      } finally {
        setBusy(false);
      }
      return;
    }

    onFeedback(command.raw ? `Unknown function: ${command.raw}` : 'Enter a function code to continue');
  };

  const onInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      const nextIndex = Math.min(historyIndexRef.current + 1, historyRef.current.length - 1);
      historyIndexRef.current = nextIndex;
      setValue(historyRef.current[nextIndex]);
      return;
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      const nextIndex = Math.max(historyIndexRef.current - 1, -1);
      historyIndexRef.current = nextIndex;
      setValue(nextIndex === -1 ? '' : historyRef.current[nextIndex]);
      return;
    }

    if (event.key === 'Escape') {
      historyIndexRef.current = -1;
      setValue('');
    }
  };

  return (
    <form
      onSubmit={onSubmit}
      className="flex h-11 items-center gap-3 border-b border-terminal-line bg-[#0b1119] px-3"
    >
      <span className="text-xs font-semibold uppercase tracking-widest text-terminal-accent">Cmd</span>
      <input
        ref={inputRef}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={onInputKeyDown}
        className="h-7 flex-1 border border-[#233044] bg-[#05080d] px-2 text-sm text-[#d7e2f0] outline-none ring-terminal-accent focus:ring-1"
        placeholder="MMAP | INTRA AAPL | WL ADD EURUSD | ALRT ADD AAPL ABOVE 200"
        spellCheck={false}
      />
      <div className="text-[11px] text-terminal-muted">
        {busy ? 'Running command...' : '↑/↓ history · Ctrl/Cmd+K focus · Ctrl/Cmd+Shift+←/→ cycle panels'}
      </div>
    </form>
  );
}
