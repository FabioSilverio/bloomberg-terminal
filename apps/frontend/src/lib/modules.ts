export const MODULES = [
  'MMAP',
  'INTRA',
  'EQRT',
  'WL',
  'EQ',
  'ECOF',
  'NEWS',
  'PORT',
  'EQS',
  'FI',
  'FA',
  'GP',
  'FX',
  'CMDT',
  'CRYPTO',
  'MSG'
] as const;

export type ModuleCode = (typeof MODULES)[number];

export interface CommandContext {
  symbol?: string;
}

export type TerminalCommand =
  | { type: 'open-module'; module: ModuleCode; context?: CommandContext }
  | { type: 'watchlist-add'; symbol: string }
  | { type: 'watchlist-remove'; symbol: string }
  | { type: 'set-mmap-refresh'; intervalMs: number }
  | { type: 'unknown'; raw: string };

export function normalizeSymbolToken(raw: string): string {
  return raw.trim().toUpperCase().replace(/\s+/g, '').replace(/[^A-Z0-9=/.\-^]/g, '');
}

function parseMmapRefresh(tokens: string[]): TerminalCommand | null {
  if (tokens.length < 3 || tokens[0] !== 'MMAP' || tokens[1] !== 'REFRESH') {
    return null;
  }

  const value = tokens[2].trim();
  const millisecondsSuffix = value.endsWith('MS');
  const numeric = Number(value.replace(/MS$/i, '').replace(/S$/i, ''));

  if (!Number.isFinite(numeric) || numeric <= 0) {
    return { type: 'unknown', raw: `MMAP REFRESH ${value}` };
  }

  const intervalMs = millisecondsSuffix ? Math.round(numeric) : Math.round(numeric * 1000);
  return { type: 'set-mmap-refresh', intervalMs: Math.max(500, intervalMs) };
}

export function parseCommand(rawInput: string): TerminalCommand {
  const raw = rawInput.trim();
  if (!raw) {
    return { type: 'unknown', raw: '' };
  }

  const upper = raw.toUpperCase().replace(/\s+/g, ' ').trim();
  const tokens = upper.split(' ');
  const [keyword, arg1, arg2] = tokens;

  const refreshCommand = parseMmapRefresh(tokens);
  if (refreshCommand) {
    return refreshCommand;
  }

  if (keyword === 'EQRT' || keyword === 'INTRA') {
    const symbol = normalizeSymbolToken(arg1 ?? 'AAPL') || 'AAPL';
    return {
      type: 'open-module',
      module: 'INTRA',
      context: { symbol }
    };
  }

  if (keyword === 'WL') {
    if (!arg1) {
      return { type: 'open-module', module: 'WL' };
    }

    if (arg1 === 'ADD' && arg2) {
      const symbol = normalizeSymbolToken(arg2);
      if (!symbol) {
        return { type: 'unknown', raw: rawInput };
      }
      return { type: 'watchlist-add', symbol };
    }

    if ((arg1 === 'DEL' || arg1 === 'REMOVE' || arg1 === 'RM') && arg2) {
      const symbol = normalizeSymbolToken(arg2);
      if (!symbol) {
        return { type: 'unknown', raw: rawInput };
      }
      return { type: 'watchlist-remove', symbol };
    }

    return { type: 'open-module', module: 'WL' };
  }

  if (MODULES.includes(keyword as ModuleCode)) {
    return {
      type: 'open-module',
      module: keyword as ModuleCode
    };
  }

  return {
    type: 'unknown',
    raw: rawInput
  };
}
