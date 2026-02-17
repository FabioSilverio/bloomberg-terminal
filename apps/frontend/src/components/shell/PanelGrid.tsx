'use client';

import GridLayout, { Layout, WidthProvider } from 'react-grid-layout';
import { useMemo } from 'react';

import { ModulePanel } from '@/components/shell/ModulePanel';
import { ModuleRenderer } from '@/components/shell/ModuleRenderer';
import { useTerminalStore } from '@/store/useTerminalStore';

const COLS = 12;
const AutoGridLayout = WidthProvider(GridLayout);

export function PanelGrid() {
  const panels = useTerminalStore((state) => state.panels);
  const layout = useTerminalStore((state) => state.layout);
  const activePanelId = useTerminalStore((state) => state.activePanelId);
  const densityMode = useTerminalStore((state) => state.densityMode);
  const setLayout = useTerminalStore((state) => state.setLayout);
  const setActivePanel = useTerminalStore((state) => state.setActivePanel);
  const closePanel = useTerminalStore((state) => state.closePanel);

  const rowHeight = densityMode === 'compact' ? 24 : 30;
  const margin: [number, number] = densityMode === 'compact' ? [6, 6] : [8, 8];

  const normalizedLayout = useMemo(
    () =>
      panels.map((panel) => {
        const existing = layout.find((item) => item.i === panel.id);
        return (
          existing ?? {
            i: panel.id,
            x: 0,
            y: Infinity,
            w: 6,
            h: 10,
            minW: 3,
            minH: 8
          }
        );
      }),
    [layout, panels]
  );

  return (
    <div className="flex-1 overflow-auto p-2">
      <AutoGridLayout
        className="layout"
        cols={COLS}
        rowHeight={rowHeight}
        layout={normalizedLayout}
        onLayoutChange={(nextLayout: Layout[]) => setLayout(nextLayout)}
        draggableHandle=".panel-handle"
        margin={margin}
      >
        {panels.map((panel) => (
          <div key={panel.id} onMouseDown={() => setActivePanel(panel.id)}>
            <ModulePanel
              title={panel.title}
              moduleCode={panel.module}
              isActive={activePanelId === panel.id}
              canClose={panels.length > 1}
              onClose={() => closePanel(panel.id)}
            >
              <ModuleRenderer panel={panel} />
            </ModulePanel>
          </div>
        ))}
      </AutoGridLayout>
    </div>
  );
}
