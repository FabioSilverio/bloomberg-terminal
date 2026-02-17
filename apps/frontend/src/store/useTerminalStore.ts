import { create } from 'zustand';
import { Layout } from 'react-grid-layout';
import { ModuleCode } from '@/lib/modules';

export interface PanelConfig {
  id: string;
  module: ModuleCode;
  title: string;
}

interface TerminalState {
  panels: PanelConfig[];
  layout: Layout[];
  commandFeedback: string;
  setLayout: (layout: Layout[]) => void;
  openModule: (module: ModuleCode) => void;
  focusPanel: (panelId: string) => void;
  setCommandFeedback: (feedback: string) => void;
}

const MODULE_TITLES: Record<ModuleCode, string> = {
  MMAP: 'Market Overview',
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
  commandFeedback: 'Type a function code (MMAP, EQ, NEWS...) and press Enter',
  setLayout: (layout) => set({ layout }),
  setCommandFeedback: (commandFeedback) => set({ commandFeedback }),
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
  openModule: (module) => {
    const { panels, layout } = get();
    const existing = panels.find((panel) => panel.module === module);

    if (existing) {
      set({
        commandFeedback: `${module} already open in panel ${existing.id.toUpperCase()}`
      });
      return;
    }

    const nextId = `${module.toLowerCase()}-${Date.now().toString(36)}`;
    const panelCount = panels.length;
    const nextPanel: PanelConfig = {
      id: nextId,
      module,
      title: MODULE_TITLES[module]
    };

    const nextLayout: Layout = {
      i: nextId,
      x: (panelCount * 3) % 12,
      y: Infinity,
      w: 6,
      h: 10,
      minW: 3,
      minH: 8
    };

    set({
      panels: [...panels, nextPanel],
      layout: [...layout, nextLayout],
      commandFeedback: `Opened ${module} in a new panel`
    });
  }
}));
