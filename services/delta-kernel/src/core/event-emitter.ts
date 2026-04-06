/**
 * Event Emitter — NATS-backed event bus for Pre Atlas.
 *
 * Publishes events to NATS topics. Gracefully degrades to no-op
 * if NATS is unavailable (system continues to work without real-time push).
 *
 * Topics:
 *   mode.changed    — mode transition occurred
 *   loop.closed     — a loop was closed or archived
 *   task.completed  — a work queue job completed
 *   approval.pending — new approval requested (future)
 */

import { connect, NatsConnection, StringCodec } from 'nats';
import { randomUUID } from 'crypto';

let nc: NatsConnection | null = null;
let connecting = false;
let lastError = 0;
const sc = StringCodec();

const NATS_URL = process.env.NATS_URL || 'nats://localhost:4222';
const RECONNECT_COOLDOWN_MS = 10_000; // Don't retry more than once per 10s

async function getConnection(): Promise<NatsConnection | null> {
  if (nc && !nc.isClosed()) return nc;
  if (connecting) return null;

  // Cooldown to prevent connection storm
  if (Date.now() - lastError < RECONNECT_COOLDOWN_MS) return null;

  connecting = true;
  try {
    nc = await connect({
      servers: NATS_URL,
      maxReconnectAttempts: 5,
      reconnectTimeWait: 2000,
    });

    // Handle unexpected closure
    nc.closed().then(() => {
      console.log('[EventBus] NATS connection closed');
      nc = null;
    });

    console.log('[EventBus] Connected to NATS at', NATS_URL);
    return nc;
  } catch (err) {
    lastError = Date.now();
    console.warn('[EventBus] NATS unavailable, events will not be published:', (err as Error).message);
    nc = null;
    return null;
  } finally {
    connecting = false;
  }
}

export async function emitEvent(topic: string, data: Record<string, unknown>): Promise<void> {
  const conn = await getConnection();
  if (!conn) return; // Graceful degradation — no NATS, no push

  const payload = JSON.stringify({
    id: randomUUID(),
    timestamp: Date.now(),
    source: 'delta-kernel',
    topic,
    data,
  });

  conn.publish(topic, sc.encode(payload));
}

export async function closeEventBus(): Promise<void> {
  if (nc && !nc.isClosed()) {
    await nc.drain();
    nc = null;
  }
}
