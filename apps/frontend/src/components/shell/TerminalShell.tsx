'use client';

import { useRef } from 'react';
import { CommandBar } from '@/components/shell/CommandBar';
import { PanelGrid } from '@/components/shell/PanelGrid';
import { StatusBar } from '@/components/shell/StatusBar';
import { useTerminalStore } from '@/store/useTerminalStore';
import { useHotkeys } from '@/hooks/useHotkeys';

export function TerminalShell() {
  const inputRef = useRef<HTMLInputElement | null>(null);

  const openModule = useTerminalStore((state) => state.openModule);
  const commandFeedback = useTerminalStore((state) => state.commandFeedback);
  const setCommandFeedback = useTerminalStore((state) => state.setCommandFeedback);

  useHotkeys({
    focusCommandBar: () => inputRef.current?.focus(),
    openModule
  });

  return (
    <main className="flex h-screen flex-col bg-terminal-bg text-[#d7e2f0]">
      <header className="flex h-9 items-center justify-between border-b border-terminal-line bg-[#070c13] px-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold uppercase tracking-wider text-terminal-accent">OpenBloom</span>
          <span className="text-[11px] uppercase tracking-wide text-terminal-muted">Terminal</span>
        </div>
        <div className="text-[11px] uppercase tracking-wide text-terminal-muted">Workspace: Default</div>
      </header>

      <CommandBar inputRef={inputRef} onOpenModule={openModule} onFeedback={setCommandFeedback} />
      <PanelGrid />
      <StatusBar feedback={commandFeedback} />
    </main>
  );
}
