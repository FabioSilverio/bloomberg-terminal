'use client';

import { useEffect, useRef } from 'react';
import clsx from 'clsx';

import { AlertToasts } from '@/components/shell/AlertToasts';
import { CommandBar } from '@/components/shell/CommandBar';
import { PanelGrid } from '@/components/shell/PanelGrid';
import { StatusBar } from '@/components/shell/StatusBar';
import { useTerminalStore } from '@/store/useTerminalStore';
import { useHotkeys } from '@/hooks/useHotkeys';

const MMAP_REFRESH_STORAGE_KEY = 'openbloom:mmap-refresh-ms';
const ALERT_SOUND_STORAGE_KEY = 'openbloom:alert-sound-enabled';

export function TerminalShell() {
  const inputRef = useRef<HTMLInputElement | null>(null);

  const openModule = useTerminalStore((state) => state.openModule);
  const activePanelId = useTerminalStore((state) => state.activePanelId);
  const closePanel = useTerminalStore((state) => state.closePanel);
  const cyclePanels = useTerminalStore((state) => state.cyclePanels);
  const densityMode = useTerminalStore((state) => state.densityMode);
  const toggleDensity = useTerminalStore((state) => state.toggleDensity);
  const commandFeedback = useTerminalStore((state) => state.commandFeedback);
  const setCommandFeedback = useTerminalStore((state) => state.setCommandFeedback);
  const setMmapRefreshMs = useTerminalStore((state) => state.setMmapRefreshMs);
  const alertSoundEnabled = useTerminalStore((state) => state.alertSoundEnabled);
  const setAlertSoundEnabled = useTerminalStore((state) => state.setAlertSoundEnabled);

  useHotkeys({
    focusCommandBar: () => inputRef.current?.focus(),
    openModule,
    cyclePanels,
    closeActivePanel: () => {
      if (activePanelId) {
        closePanel(activePanelId);
      }
    },
    toggleDensity
  });

  useEffect(() => {
    const storedRefresh = window.localStorage.getItem(MMAP_REFRESH_STORAGE_KEY);
    if (storedRefresh) {
      const parsed = Number(storedRefresh);
      if (Number.isFinite(parsed) && parsed > 0) {
        setMmapRefreshMs(parsed);
      }
    }

    const storedSound = window.localStorage.getItem(ALERT_SOUND_STORAGE_KEY);
    if (storedSound !== null) {
      setAlertSoundEnabled(storedSound === 'true');
    }
  }, [setAlertSoundEnabled, setMmapRefreshMs]);

  const handleMmapRefresh = (refreshMs: number) => {
    setMmapRefreshMs(refreshMs);
    window.localStorage.setItem(MMAP_REFRESH_STORAGE_KEY, String(refreshMs));
  };

  useEffect(() => {
    window.localStorage.setItem(ALERT_SOUND_STORAGE_KEY, String(alertSoundEnabled));
  }, [alertSoundEnabled]);

  return (
    <main
      className={clsx(
        'flex h-screen flex-col bg-terminal-bg text-[#d7e2f0]',
        densityMode === 'compact' ? 'density-compact' : 'density-normal'
      )}
    >
      <header className="flex h-9 items-center justify-between border-b border-terminal-line bg-[#070c13] px-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold uppercase tracking-wider text-terminal-accent">OpenBloom</span>
          <span className="text-[11px] uppercase tracking-wide text-terminal-muted">Terminal</span>
        </div>
        <div className="text-[11px] uppercase tracking-wide text-terminal-muted">Workspace: Default</div>
      </header>

      <AlertToasts />
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
