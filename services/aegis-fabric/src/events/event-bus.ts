/**
 * Aegis Enterprise Fabric — Event Bus
 *
 * In-process typed EventEmitter wrapper for internal events.
 */

import { EventEmitter } from 'events';
import { WebhookEventType } from '../core/types.js';

export type AegisEvent = WebhookEventType | 'system.startup' | 'system.shutdown' | 'snapshot.created';

export class AegisEventBus {
  private emitter: EventEmitter;
  private history: Array<{ event: string; data: unknown; timestamp: number }> = [];
  private maxHistory: number;

  constructor(maxHistory: number = 1000) {
    this.emitter = new EventEmitter();
    this.emitter.setMaxListeners(50);
    this.maxHistory = maxHistory;
  }

  emit(event: string, data: unknown): void {
    this.history.push({ event, data, timestamp: Date.now() });
    if (this.history.length > this.maxHistory) {
      this.history = this.history.slice(-this.maxHistory);
    }
    this.emitter.emit(event, data);
    this.emitter.emit('*', { event, data }); // wildcard listener
  }

  on(event: string, handler: (data: unknown) => void): void {
    this.emitter.on(event, handler);
  }

  off(event: string, handler: (data: unknown) => void): void {
    this.emitter.off(event, handler);
  }

  onAll(handler: (payload: { event: string; data: unknown }) => void): void {
    this.emitter.on('*', handler);
  }

  getRecentEvents(limit: number = 50): Array<{ event: string; data: unknown; timestamp: number }> {
    return this.history.slice(-limit);
  }
}
