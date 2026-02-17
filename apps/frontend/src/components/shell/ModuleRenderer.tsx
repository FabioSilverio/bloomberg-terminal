import { AlertsPanel } from '@/components/modules/AlertsPanel';
import { IntradayPanel } from '@/components/modules/IntradayPanel';
import { MMapPanel } from '@/components/modules/MMapPanel';
import { PlaceholderPanel } from '@/components/modules/PlaceholderPanel';
import { WatchlistPanel } from '@/components/modules/WatchlistPanel';
import { PanelConfig } from '@/store/useTerminalStore';

export function ModuleRenderer({ panel }: { panel: PanelConfig }) {
  switch (panel.module) {
    case 'MMAP':
      return <MMapPanel />;
    case 'INTRA':
    case 'EQRT':
      return <IntradayPanel panelId={panel.id} initialSymbol={panel.context?.symbol ?? 'AAPL'} />;
    case 'WL':
      return <WatchlistPanel />;
    case 'ALRT':
      return <AlertsPanel panelId={panel.id} initialSymbol={panel.context?.symbol} />;
    default:
      return <PlaceholderPanel module={panel.module} />;
  }
}
