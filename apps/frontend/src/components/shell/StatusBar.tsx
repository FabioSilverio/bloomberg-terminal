'use client';

import { useEffect, useMemo, useState } from 'react';

interface StatusBarProps {
  feedback: string;
}

const ZONES = [
  { label: 'UTC', zone: 'UTC' },
  { label: 'NY', zone: 'America/New_York' },
  { label: 'LON', zone: 'Europe/London' },
  { label: 'TYO', zone: 'Asia/Tokyo' }
] as const;

function formatClock(date: Date, zone: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: zone,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).format(date);
}

export function StatusBar({ feedback }: StatusBarProps) {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1_000);
    return () => window.clearInterval(timer);
  }, []);

  const clocks = useMemo(
    () => ZONES.map((zone) => ({ ...zone, value: formatClock(now, zone.zone) })),
    [now]
  );

  return (
    <footer className="flex h-8 items-center justify-between border-t border-terminal-line bg-[#0b1119] px-3 text-[11px] text-terminal-muted">
      <div className="max-w-[65%] truncate text-[#aab6c7]">{feedback}</div>
      <div className="flex items-center gap-4">
        {clocks.map((clock) => (
          <span key={clock.label} className="font-semibold text-[#d3dfef]">
            {clock.label} <span className="text-terminal-accent">{clock.value}</span>
          </span>
        ))}
      </div>
    </footer>
  );
}
