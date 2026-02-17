export const MODULES = [
  'MMAP',
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

export type TerminalCommand =
  | { type: 'open-module'; module: ModuleCode }
  | { type: 'unknown'; raw: string };

export function parseCommand(rawInput: string): TerminalCommand {
  const raw = rawInput.trim().toUpperCase();

  if (!raw) {
    return { type: 'unknown', raw: '' };
  }

  if (MODULES.includes(raw as ModuleCode)) {
    return {
      type: 'open-module',
      module: raw as ModuleCode
    };
  }

  const [keyword] = raw.split(' ');
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
