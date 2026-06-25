/**
 * WebSocket Gateway — Pre Atlas Event Bus → Browser Push
 *
 * Subscribes to NATS topics, forwards events to connected Socket.IO clients.
 * Clients receive real-time updates without polling.
 *
 * Port: 3011 (configurable via WS_PORT env var)
 */

import { Server } from 'socket.io';
import { connect, StringCodec, NatsConnection, Subscription } from 'nats';

const WS_PORT = parseInt(process.env.WS_PORT || '3011', 10);
const NATS_URL = process.env.NATS_URL || 'nats://localhost:4222';

// All topics this gateway forwards to clients
const TOPICS = [
  'mode.changed',
  'loop.closed',
  'task.completed',
  'approval.pending',
  'approval.resolved',
];

const sc = StringCodec();

async function main(): Promise<void> {
  // === Socket.IO Server ===
  const io = new Server(WS_PORT, {
    cors: { origin: '*', methods: ['GET', 'POST'] },
    pingInterval: 25000,
    pingTimeout: 20000,
  });

  console.log(`[ws-gateway] Socket.IO listening on :${WS_PORT}`);

  // === NATS Connection (with retry) ===
  let nc: NatsConnection | null = null;
  const subs: Subscription[] = [];

  async function connectNats(): Promise<void> {
    try {
      nc = await connect({
        servers: NATS_URL,
        maxReconnectAttempts: -1, // Retry forever
        reconnectTimeWait: 2000,
      });

      console.log(`[ws-gateway] Connected to NATS at ${NATS_URL}`);

      // Handle unexpected closure
      nc.closed().then((err) => {
        console.warn('[ws-gateway] NATS connection closed:', err?.message || 'clean');
        nc = null;
        // Retry after delay
        setTimeout(connectNats, 5000);
      });

      // Subscribe to all topics and forward to Socket.IO
      for (const topic of TOPICS) {
        const sub = nc.subscribe(topic);
        subs.push(sub);

        (async () => {
          for await (const msg of sub) {
            try {
              const payload = JSON.parse(sc.decode(msg.data));
              // Broadcast to all connected clients
              io.emit(topic, payload);
            } catch (err) {
              console.error(`[ws-gateway] Failed to parse message on ${topic}:`, (err as Error).message);
            }
          }
        })();
      }

      console.log(`[ws-gateway] Subscribed to ${TOPICS.length} topics: ${TOPICS.join(', ')}`);
    } catch (err) {
      console.warn(`[ws-gateway] NATS unavailable (${(err as Error).message}), retrying in 5s...`);
      setTimeout(connectNats, 5000);
    }
  }

  await connectNats();

  // === Socket.IO Connection Handling ===
  let clientCount = 0;

  io.on('connection', (socket) => {
    clientCount++;
    console.log(`[ws-gateway] Client connected: ${socket.id} (${clientCount} total)`);

    // Send current topic list so client knows what's available
    socket.emit('topics', TOPICS);

    socket.on('disconnect', () => {
      clientCount--;
      console.log(`[ws-gateway] Client disconnected: ${socket.id} (${clientCount} total)`);
    });
  });

  // === Graceful Shutdown ===
  const shutdown = async () => {
    console.log('[ws-gateway] Shutting down...');
    for (const sub of subs) {
      sub.unsubscribe();
    }
    if (nc && !nc.isClosed()) {
      await nc.drain();
    }
    io.close();
    process.exit(0);
  };

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

main().catch((err) => {
  console.error('[ws-gateway] Fatal error:', err);
  process.exit(1);
});
