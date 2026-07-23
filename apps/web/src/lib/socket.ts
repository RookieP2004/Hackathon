import { io, type Socket } from 'socket.io-client';

/**
 * Realtime Gateway client (ARCHITECTURE.md §11.2) — the "hot state" transport for
 * live telemetry, risk feeds, and the Digital Twin scene. This module is a thin
 * singleton wrapper; actual channel subscriptions (zone-scoped filtering per
 * §11.2) are implemented in DEVELOPMENT_ROADMAP.md M157-M159, not here.
 */
let socket: Socket | null = null;

export function getRealtimeSocket(): Socket {
  if (!socket) {
    socket = io(process.env.NEXT_PUBLIC_WS_URL ?? 'ws://127.0.0.1:8001', {
      autoConnect: false,
      transports: ['websocket'],
    });
  }
  return socket;
}
