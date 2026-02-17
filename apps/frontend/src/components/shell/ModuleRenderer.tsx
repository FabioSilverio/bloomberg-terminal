import { MMapPanel } from '@/components/modules/MMapPanel';
import { PlaceholderPanel } from '@/components/modules/PlaceholderPanel';
import { ModuleCode } from '@/lib/modules';

export function ModuleRenderer({ module }: { module: ModuleCode }) {
  switch (module) {
    case 'MMAP':
      return <MMapPanel />;
    default:
      return <PlaceholderPanel module={module} />;
  }
}
