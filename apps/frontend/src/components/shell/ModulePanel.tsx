'use client';

import { ReactNode } from 'react';
import clsx from 'clsx';

interface ModulePanelProps {
  title: string;
  moduleCode: string;
  isActive?: boolean;
  canClose?: boolean;
  onClose?: () => void;
  children: ReactNode;
}

export function ModulePanel({ title, moduleCode, isActive, canClose, onClose, children }: ModulePanelProps) {
  return (
    <article
      className={clsx(
        'flex h-full flex-col border bg-terminal-panel shadow-terminal',
        isActive ? 'border-[#ff8a00]' : 'border-terminal-line'
      )}
    >
      <header className="panel-handle flex h-7 cursor-move items-center justify-between border-b border-terminal-line bg-[#0e151f] px-2">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-terminal-accent">{moduleCode}</div>
        <div className="truncate px-2 text-[11px] text-[#d2dded]">{title}</div>
        <button
          type="button"
          disabled={!canClose}
          onClick={(event) => {
            event.stopPropagation();
            onClose?.();
          }}
          className="h-5 w-5 border border-terminal-line bg-[#101926] text-[10px] text-terminal-muted disabled:opacity-40"
          title="Close panel (Ctrl/Cmd + Shift + X)"
        >
          ×
        </button>
      </header>
      <div className="min-h-0 flex-1">{children}</div>
    </article>
  );
}
