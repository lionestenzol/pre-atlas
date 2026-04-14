/**
 * Aegis Enterprise Fabric — Approval Routes
 * GET  /api/v1/approvals     — List pending approvals
 * POST /api/v1/approvals/:id — Approve or reject
 */

import { Router, Request, Response } from 'express';
import { ApprovalQueue } from '../../approval/approval-queue.js';
import { ActionProcessor } from '../../agents/action-processor.js';
import { logger } from '../../observability/logger.js';
import { CanonicalAgentAction } from '../../core/types.js';

export function approvalRoutes(
  approvalQueue: ApprovalQueue,
  actionProcessor: ActionProcessor
): Router {
  const router = Router();

  router.get('/api/v1/approvals', (req: Request, res: Response) => {
    if (!req.tenant) {
      res.status(401).json({ error: 'Tenant authentication required' });
      return;
    }

    // Check for expired approvals
    approvalQueue.checkExpirations(req.tenant.id);

    const pending = approvalQueue.listPending(req.tenant.id);
    res.json({
      pending: pending.map(p => ({
        approval_id: p.entity.entity_id,
        action: p.data.action,
        agent_id: p.data.agent_id,
        params: p.data.params,
        requested_at: p.data.requested_at,
        expires_at: p.data.expires_at,
      })),
    });
  });

  router.post('/api/v1/approvals/:id', async (req: Request, res: Response) => {
    try {
      if (!req.tenant) {
        res.status(401).json({ error: 'Tenant authentication required' });
        return;
      }

      const approvalId = String(req.params.id);
      const { decision, reason } = req.body;

      if (!decision || !['APPROVED', 'REJECTED'].includes(decision)) {
        res.status(400).json({ error: 'decision must be APPROVED or REJECTED' });
        return;
      }

      const approval = approvalQueue.getApproval(req.tenant.id, approvalId);
      if (!approval) {
        res.status(404).json({ error: 'Approval not found' });
        return;
      }

      const result = approvalQueue.decide(
        req.tenant.id,
        approvalId,
        decision,
        'api-user',
        reason
      );

      if (!result) {
        res.status(409).json({ error: 'Approval already decided or expired' });
        return;
      }

      logger.info('Approval decided', { approval_id: approvalId, decision });

      // If approved, re-execute the held action
      if (decision === 'APPROVED') {
        const action: CanonicalAgentAction = {
          action_id: approval.data.action_id,
          tenant_id: approval.data.tenant_id,
          agent_id: approval.data.agent_id,
          agent_version: '1.0.0',
          action: approval.data.action,
          params: approval.data.params,
          metadata: { provider: 'custom' },
          timestamp: Date.now(),
        };

        const execResult = await actionProcessor.process(action);
        res.json({ approval: result, execution: execResult });
        return;
      }

      res.json({ approval: result });
    } catch (err) {
      logger.error('Approval decision failed', { error: String(err) });
      res.status(500).json({ error: 'Approval decision failed' });
    }
  });

  return router;
}
