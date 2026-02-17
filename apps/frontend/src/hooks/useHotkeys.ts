'use client';

import { useEffect } from 'react';

import { CommandContext, ModuleCode } from '@/lib/modules';

interface UseHotkeysArgs {
  focusCommandBar: () => void;
  openModule: (code: ModuleCode, context?: CommandContext) => void;
}

export function useHotkeys({ focusCommandBar, openModule }: UseHotkeysArgs) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        focusCommandBar();
      }

      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'm') {
        event.preventDefault();
        openModule('MMAP');
      }

      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'i') {
        event.preventDefault();
        openModule('INTRA', { symbol: 'AAPL' });
      }

      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'w') {
        event.preventDefault();
        openModule('WL');
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [focusCommandBar, openModule]);
}
