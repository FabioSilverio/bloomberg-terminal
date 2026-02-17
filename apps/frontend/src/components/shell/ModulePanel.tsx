'use client';

import { ReactNode } from 'react';

interface ModulePanelProps {
  title: string;
  moduleCode: string;
  children: ReactNode;
}

export function ModulePanel({ title, moduleCode, children }: ModulePanelProps) {
  return (
    <article className="flex h-full flex-col border border-terminal-line bg-terminal-panel shadow-terminal">
      <header className="panel-handle flex h-8 cursor-move items-center justify-between border-b border-terminal-line bg-[#0e151f] px-2">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-terminal-accent">{moduleCode}</div>
        <div className="truncate px-2 text-xs text-[#d2dded]">{title}</div>
      </header>
      <div className="min-h-0 flex-1">{children}</div>
    </article>
  );
}
