/**
 * Aegis Enterprise Fabric — Webhook Dispatcher
 *
 * Dispatches webhook POSTs with HMAC-SHA256 signing and exponential backoff retries.
 */

import * as crypto from 'crypto';
import { UUID, WebhookData, WebhookEventType, Entity } from '../core/types.js';
import { AegisStorage } from '../storage/aegis-storage.js';
import { AegisEventBus } from './event-bus.js';

const MAX_RETRIES = 3;
const BACKOFF_BASE_MS = 1000;

export class WebhookDispatcher {
  private storage: AegisStorage;
  private eventBus: AegisEventBus;

  constructor(storage: AegisStorage, eventBus: AegisEventBus) {
    this.storage = storage;
    this.eventBus = eventBus;

    // Listen to all events and dispatch matching webhooks
    this.eventBus.onAll((payload) => {
      this.dispatchForEvent(payload.event, payload.data);
    });
  }

  private async dispatchForEvent(event: string, data: unknown): Promise<void> {
    // Find all tenants' webhooks that match this event
    // For prototype, we check if event matches a WebhookEventType
    const eventType = event as WebhookEventType;

    // We need tenant_id from the data
    const tenantId = (data as Record<string, unknown>)?.tenant_id as string
      || ((data as Record<string, unknown>)?.action as Record<string, unknown>)?.tenant_id as string;
    if (!tenantId) return;

    const webhooks = this.storage.loadEntitiesByType<WebhookData>(tenantId, 'aegis_webhook');
    for (const { entity, state: webhook } of webhooks) {
      if (!webhook.enabled) continue;
      if (!webhook.events.includes(eventType)) continue;

      this.deliver(webhook, entity, tenantId, event, data);
    }
  }

  private async deliver(
    webhook: WebhookData,
    entity: Entity,
    tenantId: UUID,
    event: string,
    data: unknown,
    attempt: number = 0
  ): Promise<void> {
    const body = JSON.stringify({
      event,
      tenant_id: tenantId,
      timestamp: Date.now(),
      data,
    });

    // HMAC signing
    const signature = crypto
      .createHmac('sha256', webhook.secret_hash)
      .update(body)
      .digest('hex');

    try {
      const response = await fetch(webhook.url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Aegis-Signature': signature,
          'X-Aegis-Event': event,
        },
        body,
        signal: AbortSignal.timeout(10_000),  // 10s timeout
      });

      if (!response.ok && attempt < MAX_RETRIES) {
        const delay = BACKOFF_BASE_MS * Math.pow(4, attempt);
        setTimeout(() => this.deliver(webhook, entity, tenantId, event, data, attempt + 1), delay);
        return;
      }

      // Update webhook state
      webhook.last_triggered_at = Date.now();
      if (!response.ok) {
        webhook.failure_count += 1;
      }
      this.storage.saveEntity(tenantId, entity, webhook);
    } catch {
      if (attempt < MAX_RETRIES) {
        const delay = BACKOFF_BASE_MS * Math.pow(4, attempt);
        setTimeout(() => this.deliver(webhook, entity, tenantId, event, data, attempt + 1), delay);
      } else {
        webhook.failure_count += 1;
        webhook.last_triggered_at = Date.now();
        this.storage.saveEntity(tenantId, entity, webhook);
      }
    }
  }

  /**
   * Register a webhook for a tenant.
   */
  async registerWebhook(tenantId: UUID, opts: {
    url: string;
    events: WebhookEventType[];
    secret?: string;
  }): Promise<{ webhookId: UUID }> {
    const { createEntity } = await import('../core/delta.js');

    const webhookData: WebhookData = {
      tenant_id: tenantId,
      url: opts.url,
      events: opts.events,
      secret_hash: opts.secret || crypto.randomBytes(16).toString('hex'),
      enabled: true,
      retry_count: MAX_RETRIES,
      last_triggered_at: null,
      failure_count: 0,
      created_at: Date.now(),
    };

    const { entity, delta } = await createEntity('aegis_webhook', webhookData, tenantId);
    this.storage.saveEntity(tenantId, entity, webhookData);
    this.storage.appendDelta(tenantId, delta);

    return { webhookId: entity.entity_id };
  }

  listWebhooks(tenantId: UUID): Array<{ entity: Entity; data: WebhookData }> {
    return this.storage.loadEntitiesByType<WebhookData>(tenantId, 'aegis_webhook')
      .map(w => ({ entity: w.entity, data: w.state }));
  }
}
