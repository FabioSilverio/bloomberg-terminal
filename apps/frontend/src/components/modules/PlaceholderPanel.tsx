interface PlaceholderPanelProps {
  module: string;
}

export function PlaceholderPanel({ module }: PlaceholderPanelProps) {
  return (
    <div className="flex h-full flex-col bg-terminal-panel">
      <div className="border-b border-terminal-line px-3 py-2 text-xs uppercase tracking-wider text-terminal-muted">
        {module} module queued
      </div>
      <div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-[#95a3b8]">
        <div>
          <div className="mb-2 text-terminal-accent">{module}</div>
          <p>Module implementation is planned in the upcoming build phase.</p>
        </div>
      </div>
    </div>
  );
}
