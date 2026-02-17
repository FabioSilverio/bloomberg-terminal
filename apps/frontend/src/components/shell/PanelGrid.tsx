'use client';

import GridLayout, { Layout, WidthProvider } from 'react-grid-layout';
import { useMemo } from 'react';
import { useTerminalStore } from '@/store/useTerminalStore';
import { ModulePanel } from '@/components/shell/ModulePanel';
import { ModuleRenderer } from '@/components/shell/ModuleRenderer';

const COLS = 12;
const ROW_HEIGHT = 30;
const AutoGridLayout = WidthProvider(GridLayout);

export function PanelGrid() {
  const panels = useTerminalStore((state) => state.panels);
  const layout = useTerminalStore((state) => state.layout);
  const setLayout = useTerminalStore((state) => state.setLayout);

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
        rowHeight={ROW_HEIGHT}
        layout={normalizedLayout}
        onLayoutChange={(nextLayout: Layout[]) => setLayout(nextLayout)}
        draggableHandle=".panel-handle"
        margin={[8, 8]}
      >
        {panels.map((panel) => (
          <div key={panel.id}>
            <ModulePanel title={panel.title} moduleCode={panel.module}>
              <ModuleRenderer module={panel.module} />
            </ModulePanel>
          </div>
        ))}
      </AutoGridLayout>
    </div>
  );
}
