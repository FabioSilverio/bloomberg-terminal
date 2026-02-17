'use client';

import { useAlertNotifications } from '@/hooks/useAlertNotifications';

export function AlertToasts() {
  const { toasts, dismissToast } = useAlertNotifications();

  if (toasts.length === 0) {
    return null;
  }

  return (
    <div className="pointer-events-none fixed right-3 top-14 z-50 flex w-[360px] max-w-[92vw] flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="pointer-events-auto border border-[#8f7c2d] bg-[#2a2410] px-3 py-2 text-xs text-[#ffdf7a] shadow-lg"
        >
          <div className="flex items-start gap-2">
            <div className="flex-1">
              <div className="text-[10px] uppercase tracking-wide text-[#f7d57c]">ALERT TRIGGERED</div>
              <div className="mt-1 font-semibold text-[#ffe9b0]">{toast.message}</div>
              <div className="mt-1 text-[10px] text-[#d9c07a]">{new Date(toast.triggeredAt).toLocaleTimeString()}</div>
            </div>
            <button
              type="button"
              onClick={() => dismissToast(toast.id)}
              className="h-5 w-5 border border-[#9d8b4d] bg-[#3a3318] text-[10px] text-[#ffe9b0]"
            >
              ×
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
