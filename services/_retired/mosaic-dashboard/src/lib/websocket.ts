/**
 * WebSocket client for Pre Atlas real-time events.
 *
 * Connects to ws-gateway (:3006) via Socket.IO.
 * Provides typed subscription hooks for React components.
 * Falls back gracefully if gateway is unavailable.
 */

import { io, Socket } from 'socket.io-client';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'http://localhost:3006';

let socket: Socket | null = null;

function getSocket(): Socket {
  if (!socket) {
    socket = io(WS_URL, {
      transports: ['websocket', 'polling'],
      reconnectionDelay: 2000,
      reconnectionDelayMax: 10000,
      reconnectionAttempts: Infinity,
      autoConnect: true,
    });

    socket.on('connect', () => {
      console.log('[WS] Connected to event bus');
    });

    socket.on('disconnect', (reason) => {
      console.log('[WS] Disconnected:', reason);
    });

    socket.on('connect_error', () => {
      // Silent — polling fallback continues to work
    });
  }
  return socket;
}

export interface ModeChangedEvent {
  oldMode: string;
  newMode: string;
  closureRatio: number;
  openLoops: number;
  buildAllowed: boolean;
  reason: string;
}

export interface LoopClosedEvent {
  loopId: string | null;
  loopTitle: string | null;
  outcome: string;
  closedAt: string;
  newMode: string;
  modeChanged: boolean;
  closureRatio: number;
}

export interface TaskCompletedEvent {
  jobId: string;
  outcome: string;
  durationMs: number;
  queueAdvanced: boolean;
  nextJobStarted: string | null;
}

/**
 * Subscribe to mode changes. Returns unsubscribe function.
 */
export function onModeChanged(callback: (event: ModeChangedEvent) => void): () => void {
  const s = getSocket();
  const handler = (payload: { data: ModeChangedEvent }) => {
    callback(payload.data);
  };
  s.on('mode.changed', handler);
  return () => { s.off('mode.changed', handler); };
}

/**
 * Subscribe to loop closures. Returns unsubscribe function.
 */
export function onLoopClosed(callback: (event: LoopClosedEvent) => void): () => void {
  const s = getSocket();
  const handler = (payload: { data: LoopClosedEvent }) => {
    callback(payload.data);
  };
  s.on('loop.closed', handler);
  return () => { s.off('loop.closed', handler); };
}

/**
 * Subscribe to task completions. Returns unsubscribe function.
 */
export function onTaskCompleted(callback: (event: TaskCompletedEvent) => void): () => void {
  const s = getSocket();
  const handler = (payload: { data: TaskCompletedEvent }) => {
    callback(payload.data);
  };
  s.on('task.completed', handler);
  return () => { s.off('task.completed', handler); };
}

/**
 * Check if WebSocket is currently connected.
 */
export function isConnected(): boolean {
  return socket?.connected ?? false;
}
