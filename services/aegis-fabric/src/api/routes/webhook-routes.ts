/**
 * Aegis Enterprise Fabric — Webhook Routes
 * POST /api/v1/webhooks/manage — CRUD webhooks (action: create/list/delete)
 */

import { Router, Request, Response } from 'express';
import { WebhookDispatcher } from '../../events/webhook-dispatcher.js';
import { logger } from '../../observability/logger.js';

export function webhookRoutes(webhookDispatcher: WebhookDispatcher): Router {
  const router = Router();

  router.post('/api/v1/webhooks/manage', async (req: Request, res: Response) => {
    try {
      if (!req.tenant) {
        res.status(401).json({ error: 'Tenant authentication required' });
        return;
      }

      const { action } = req.body;

      switch (action) {
        case 'create': {
          const { url, events, secret } = req.body;
          if (!url || !events) {
            res.status(400).json({ error: 'url and events are required' });
            return;
          }
          const { webhookId } = await webhookDispatcher.registerWebhook(req.tenant.id, { url, events, secret });
          logger.info('Webhook created', { tenant_id: req.tenant.id, webhook_id: webhookId });
          res.status(201).json({ webhook_id: webhookId });
          return;
        }

        case 'list': {
          const webhooks = webhookDispatcher.listWebhooks(req.tenant.id);
          res.json({
            webhooks: webhooks.map(w => ({
              webhook_id: w.entity.entity_id,
              url: w.data.url,
              events: w.data.events,
              enabled: w.data.enabled,
              failure_count: w.data.failure_count,
              last_triggered_at: w.data.last_triggered_at,
            })),
          });
          return;
        }

        default:
          res.status(400).json({ error: 'action must be create or list' });
      }
    } catch (err) {
      logger.error('Webhook operation failed', { error: String(err) });
      res.status(500).json({ error: 'Webhook operation failed' });
    }
  });

  return router;
}
