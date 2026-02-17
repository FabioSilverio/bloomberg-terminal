'use client';

import { useEffect, useRef } from 'react';
import { CommandBar } from '@/components/shell/CommandBar';
import { PanelGrid } from '@/components/shell/PanelGrid';
import { StatusBar } from '@/components/shell/StatusBar';
import { useTerminalStore } from '@/store/useTerminalStore';
import { useHotkeys } from '@/hooks/useHotkeys';

const MMAP_REFRESH_STORAGE_KEY = 'openbloom:mmap-refresh-ms';

export function TerminalShell() {
  const inputRef = useRef<HTMLInputElement | null>(null);

  const openModule = useTerminalStore((state) => state.openModule);
  const commandFeedback = useTerminalStore((state) => state.commandFeedback);
  const setCommandFeedback = useTerminalStore((state) => state.setCommandFeedback);
  const setMmapRefreshMs = useTerminalStore((state) => state.setMmapRefreshMs);

  useHotkeys({
    focusCommandBar: () => inputRef.current?.focus(),
    openModule
  });

  useEffect(() => {
    const stored = window.localStorage.getItem(MMAP_REFRESH_STORAGE_KEY);
    if (!stored) {
      return;
    }

    const parsed = Number(stored);
    if (Number.isFinite(parsed) && parsed > 0) {
      setMmapRefreshMs(parsed);
    }
  }, [setMmapRefreshMs]);

  const handleMmapRefresh = (refreshMs: number) => {
    setMmapRefreshMs(refreshMs);
    window.localStorage.setItem(MMAP_REFRESH_STORAGE_KEY, String(refreshMs));
  };

  return (
    <main className="flex h-screen flex-col bg-terminal-bg text-[#d7e2f0]">
      <header className="flex h-9 items-center justify-between border-b border-terminal-line bg-[#070c13] px-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold uppercase tracking-wider text-terminal-accent">OpenBloom</span>
          <span className="text-[11px] uppercase tracking-wide text-terminal-muted">Terminal</span>
        </div>
        <div className="text-[11px] uppercase tracking-wide text-terminal-muted">Workspace: Default</div>
      </header>

      <CommandBar
        inputRef={inputRef}
        onOpenModule={openModule}
        onSetMmapRefresh={handleMmapRefresh}
        onFeedback={setCommandFeedback}
      />
      <PanelGrid />
      <StatusBar feedback={commandFeedback} />
    </main>
  );
}
