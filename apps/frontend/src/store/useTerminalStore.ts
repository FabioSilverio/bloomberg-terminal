import { create } from 'zustand';
import { Layout } from 'react-grid-layout';
import { CommandContext, ModuleCode, normalizeSymbolToken } from '@/lib/modules';

export interface PanelConfig {
  id: string;
  module: ModuleCode;
  title: string;
  context?: CommandContext;
}

interface TerminalState {
  panels: PanelConfig[];
  layout: Layout[];
  commandFeedback: string;
  mmapRefreshMs: number;
  setLayout: (layout: Layout[]) => void;
  openModule: (module: ModuleCode, context?: CommandContext) => void;
  focusPanel: (panelId: string) => void;
  setPanelContext: (panelId: string, context: CommandContext) => void;
  setCommandFeedback: (feedback: string) => void;
  setMmapRefreshMs: (value: number) => void;
}

const DEFAULT_MMAP_REFRESH_MS = Number(process.env.NEXT_PUBLIC_MMAP_REFRESH_INTERVAL_MS ?? 2000);

const MODULE_TITLES: Record<ModuleCode, string> = {
  MMAP: 'Market Overview',
  INTRA: 'Intraday Realtime',
  EQRT: 'Intraday Realtime',
  WL: 'Watchlist',
  EQ: 'Equities',
  ECOF: 'Economic Forecasts',
  NEWS: 'News Monitor',
  PORT: 'Portfolio Monitor',
  EQS: 'Equity Screen',
  FI: 'Fixed Income',
  FA: 'Financial Analysis',
  GP: 'Graph Panel',
  FX: 'FX Matrix',
  CMDT: 'Commodities',
  CRYPTO: 'Crypto Monitor',
  MSG: 'Messaging'
};

function buildPanelTitle(module: ModuleCode, context?: CommandContext): string {
  if ((module === 'INTRA' || module === 'EQRT') && context?.symbol) {
    return `Intraday ${context.symbol}`;
  }

  return MODULE_TITLES[module];
}

const INITIAL_PANELS: PanelConfig[] = [
  {
    id: 'mmap-main',
    module: 'MMAP',
    title: MODULE_TITLES.MMAP
  }
];

const INITIAL_LAYOUT: Layout[] = [
  {
    i: 'mmap-main',
    x: 0,
    y: 0,
    w: 12,
    h: 16,
    minW: 4,
    minH: 8
  }
];

export const useTerminalStore = create<TerminalState>((set, get) => ({
  panels: INITIAL_PANELS,
  layout: INITIAL_LAYOUT,
  mmapRefreshMs: Number.isFinite(DEFAULT_MMAP_REFRESH_MS) ? Math.max(500, DEFAULT_MMAP_REFRESH_MS) : 2000,
  commandFeedback: 'Try: MMAP | INTRA AAPL | WL | WL ADD EURUSD',
  setLayout: (layout) => set({ layout }),
  setCommandFeedback: (commandFeedback) => set({ commandFeedback }),
  setMmapRefreshMs: (value) => set({ mmapRefreshMs: Math.max(500, Math.round(value)) }),
  focusPanel: (panelId) => {
    const layout = get().layout;
    const selected = layout.find((item) => item.i === panelId);
    if (!selected) {
      return;
    }

    const reordered = [
      ...layout.filter((item) => item.i !== panelId),
      {
        ...selected,
        y: Math.min(...layout.map((item) => item.y))
      }
    ];

    set({ layout: reordered });
  },
  setPanelContext: (panelId, context) => {
    const symbol = context.symbol ? normalizeSymbolToken(context.symbol) : undefined;

    set((state) => ({
      panels: state.panels.map((panel) => {
        if (panel.id !== panelId) {
          return panel;
        }

        const nextContext: CommandContext = {
          ...panel.context,
          ...context,
          ...(symbol ? { symbol } : {})
        };

        return {
          ...panel,
          context: nextContext,
          title: buildPanelTitle(panel.module, nextContext)
        };
      })
    }));
  },
  openModule: (module, context) => {
    const normalizedModule = module === 'EQRT' ? 'INTRA' : module;
    const { panels, layout } = get();

    let normalizedContext = context;
    if (normalizedModule === 'INTRA') {
      normalizedContext = {
        ...context,
        symbol: normalizeSymbolToken(context?.symbol ?? 'AAPL') || 'AAPL'
      };
    }

    const existing = panels.find((panel) => {
      if (normalizedModule === 'INTRA') {
        return panel.module === 'INTRA' && panel.context?.symbol === normalizedContext?.symbol;
      }

      return panel.module === normalizedModule;
    });

    if (existing) {
      set({
        commandFeedback:
          normalizedModule === 'INTRA' && normalizedContext?.symbol
            ? `INTRA ${normalizedContext.symbol} already open`
            : `${normalizedModule} already open`
      });
      return;
    }

    const nextId = `${normalizedModule.toLowerCase()}-${Date.now().toString(36)}`;
    const panelCount = panels.length;
    const nextPanel: PanelConfig = {
      id: nextId,
      module: normalizedModule,
      title: buildPanelTitle(normalizedModule, normalizedContext),
      context: normalizedContext
    };

    const nextLayout: Layout = {
      i: nextId,
      x: (panelCount * 3) % 12,
      y: Infinity,
      w: normalizedModule === 'WL' ? 5 : 6,
      h: normalizedModule === 'WL' ? 12 : 10,
      minW: 3,
      minH: 8
    };

    set({
      panels: [...panels, nextPanel],
      layout: [...layout, nextLayout],
      commandFeedback:
        normalizedModule === 'INTRA' && normalizedContext?.symbol
          ? `Opened INTRA ${normalizedContext.symbol}`
          : `Opened ${normalizedModule} in a new panel`
    });
  }
}));
