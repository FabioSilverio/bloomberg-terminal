'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

import { AlertTriggerEvent, fetchAlertEvents } from '@/lib/api';
import { useTerminalStore } from '@/store/useTerminalStore';

const ALERT_STREAM_POLL_MS = Number(process.env.NEXT_PUBLIC_ALERTS_POLL_INTERVAL_MS ?? 2000);

export interface AlertToast {
  id: string;
  eventId: number;
  message: string;
  triggeredAt: string;
}

function buildToastMessage(event: AlertTriggerEvent): string {
  return `${event.symbol} ${event.condition} @ ${event.triggerPrice.toFixed(4)}`;
}

function playAlertTone() {
  try {
    const AudioContextCtor = window.AudioContext ?? (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextCtor) {
      return;
    }

    const context = new AudioContextCtor();
    const oscillator = context.createOscillator();
    const gainNode = context.createGain();

    oscillator.type = 'triangle';
    oscillator.frequency.value = 880;

    gainNode.gain.value = 0.001;
    gainNode.gain.exponentialRampToValueAtTime(0.08, context.currentTime + 0.02);
    gainNode.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.28);

    oscillator.connect(gainNode);
    gainNode.connect(context.destination);

    oscillator.start();
    oscillator.stop(context.currentTime + 0.3);

    window.setTimeout(() => {
      context.close().catch(() => undefined);
    }, 350);
  } catch {
    // no-op
  }
}

export function useAlertNotifications() {
  const [toasts, setToasts] = useState<AlertToast[]>([]);
  const soundEnabled = useTerminalStore((state) => state.alertSoundEnabled);
  const setCommandFeedback = useTerminalStore((state) => state.setCommandFeedback);

  const latestIdRef = useRef<number>(0);
  const initializedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const eventsResponse = await fetchAlertEvents({
          afterId: latestIdRef.current || undefined,
          limit: 25
        });

        if (cancelled || eventsResponse.items.length === 0) {
          initializedRef.current = true;
          return;
        }

        const ordered = [...eventsResponse.items].sort((a, b) => a.id - b.id);
        const maxId = ordered[ordered.length - 1]?.id;
        if (typeof maxId === 'number') {
          latestIdRef.current = maxId;
        }

        if (!initializedRef.current) {
          initializedRef.current = true;
          return;
        }

        const newToasts = ordered.map((event) => ({
          id: `${event.id}-${Date.now().toString(36)}`,
          eventId: event.id,
          message: buildToastMessage(event),
          triggeredAt: event.triggeredAt
        }));

        if (newToasts.length > 0) {
          setToasts((prev) => [...newToasts, ...prev].slice(0, 6));
          setCommandFeedback(`ALERT TRIGGERED: ${newToasts[0].message}`);

          if (soundEnabled) {
            playAlertTone();
          }

          newToasts.forEach((toast) => {
            window.setTimeout(() => {
              setToasts((prev) => prev.filter((entry) => entry.id !== toast.id));
            }, 6000);
          });
        }
      } catch {
        initializedRef.current = true;
      }
    };

    poll();
    const timer = window.setInterval(poll, Math.max(750, Number.isFinite(ALERT_STREAM_POLL_MS) ? ALERT_STREAM_POLL_MS : 2000));

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [setCommandFeedback, soundEnabled]);

  const dismissToast = (toastId: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== toastId));
  };

  return useMemo(
    () => ({
      toasts,
      dismissToast
    }),
    [toasts]
  );
}
