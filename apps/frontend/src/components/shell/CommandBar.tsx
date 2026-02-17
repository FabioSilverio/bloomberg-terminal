'use client';

import { FormEvent, RefObject, useState } from 'react';
import { ModuleCode, parseCommand } from '@/lib/modules';

interface CommandBarProps {
  inputRef: RefObject<HTMLInputElement | null>;
  onOpenModule: (module: ModuleCode) => void;
  onFeedback: (message: string) => void;
}

export function CommandBar({ inputRef, onOpenModule, onFeedback }: CommandBarProps) {
  const [value, setValue] = useState('MMAP');

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();

    const command = parseCommand(value);

    if (command.type === 'open-module') {
      onOpenModule(command.module);
      setValue(command.module);
      return;
    }

    onFeedback(command.raw ? `Unknown function: ${command.raw}` : 'Enter a function code to continue');
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
        className="h-7 flex-1 border border-[#233044] bg-[#05080d] px-2 text-sm text-[#d7e2f0] outline-none ring-terminal-accent focus:ring-1"
        placeholder="Type function code (MMAP, EQ, NEWS...)"
        spellCheck={false}
      />
      <div className="text-[11px] text-terminal-muted">Ctrl/Cmd+K focus | Ctrl/Cmd+Shift+M MMAP</div>
    </form>
  );
}
