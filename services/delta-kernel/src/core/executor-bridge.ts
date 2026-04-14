/**
 * Executor Bridge — Connects delta-kernel governance to UASC executor
 *
 * Maps confirmed PendingActions to UASC command tokens and fires them.
 * Results feed back as deltas into the delta state.
 */

import { ActionType, PendingActionData, UUID, DraftData } from './types-core';

// === CONFIGURATION ===

const UASC_URL = process.env.UASC_EXECUTOR_URL || 'http://localhost:3008';
const UASC_CLIENT_ID = 'delta-kernel';
const UASC_SECRET = 'delta-kernel-local-secret';

// === ACTION → TOKEN MAPPING ===

const ACTION_TOKEN_MAP: Record<ActionType, string | null> = {
  reply_message: '@SEND_DRAFT',
  complete_task: '@CLOSE_LOOP',
  send_draft: '@SEND_DRAFT',
  apply_automation: '@WORK',
  create_asset: '@BUILD',
  delegate: '@DEPLOY',
  rest_action: null,  // no-op, log only
};

// === TYPES ===

export interface ExecutionRequest {
  cmd: string;
  inputs: Record<string, string>;
}

export interface ExecutionResponse {
  run_id: string;
  cmd: string;
  status: 'success' | 'failed';
  duration_ms: number;
  steps: Array<{
    name: string;
    status: string;
    duration_ms: number;
  }>;
  outputs: Record<string, string>;
  error: string | null;
}

export interface BridgeResult {
  executed: boolean;
  run_id: string | null;
  status: 'success' | 'failed' | 'skipped';
  error: string | null;
  duration_ms: number;
}

// === HMAC SIGNING ===

async function computeSignature(secret: string, timestamp: string, body: string): Promise<string> {
  // Use Node.js crypto for HMAC-SHA256
  const crypto = await import('crypto');
  const message = `${timestamp}${body}`;
  return crypto.createHmac('sha256', secret).update(message).digest('hex');
}

// === BRIDGE FUNCTIONS ===

/**
 * Map a confirmed PendingAction to a UASC execution request.
 */
export function buildExecutionRequest(
  action: PendingActionData,
  context?: { task_title?: string; draft_data?: DraftData }
): ExecutionRequest | null {
  const token = ACTION_TOKEN_MAP[action.action_type];

  if (!token) {
    // rest_action — no execution needed
    return null;
  }

  const inputs: Record<string, string> = {};

  switch (action.action_type) {
    case 'complete_task':
      inputs.task_id = action.target_entity_id;
      inputs.task_title = context?.task_title || 'unknown';
      break;

    case 'reply_message':
    case 'send_draft':
      inputs.draft_id = action.target_entity_id;
      if (context?.draft_data) {
        inputs.template_id = context.draft_data.template_id;
        inputs.message_text = renderTemplate(
          context.draft_data.template_id,
          context.draft_data.params,
        );
        if (context.draft_data.target_entity_id) {
          inputs.target_entity_id = context.draft_data.target_entity_id;
        }
      }
      break;

    case 'create_asset':
      inputs.project_dir = (action.payload?.project_dir as string) || '.';
      break;

    case 'apply_automation':
      // Pass through any payload fields as inputs
      for (const [k, v] of Object.entries(action.payload || {})) {
        inputs[k] = String(v);
      }
      break;

    case 'delegate':
      inputs.task_id = action.target_entity_id;
      inputs.task_title = context?.task_title || 'unknown';
      break;
  }

  return { cmd: token, inputs };
}

/**
 * Simple template renderer for draft messages.
 * Matches delta-kernel's 12 locked templates.
 */
function renderTemplate(templateId: string, params: Record<string, string>): string {
  const TEMPLATES: Record<string, string> = {
    TEMPLATE_ACK: 'Acknowledged.',
    TEMPLATE_DEFER: 'I\'ll follow up {window}.',
    TEMPLATE_REQUEST: 'Can you send {item}?',
    TEMPLATE_UPDATE: 'Update: {status}.',
    TEMPLATE_CLOSE: 'Closing this thread.',
    TEMPLATE_FOLLOWUP: 'Following up on {topic}.',
    TEMPLATE_RECOVER_REST: 'I\'m offline until {time} to recover.',
    TEMPLATE_CLOSE_COMMIT: 'I will resolve this by {time}.',
    TEMPLATE_BUILD_OUTLINE: 'Here is the outline for {asset}.',
    TEMPLATE_COMPOUND_EXTEND: 'Extending {asset} with {addition}.',
    TEMPLATE_SCALE_DELEGATE: 'Please take ownership of {task}.',
    TEMPLATE_SCALE_SYSTEMIZE: 'Systemizing {process}.',
  };

  let text = TEMPLATES[templateId] || templateId;
  for (const [key, value] of Object.entries(params)) {
    text = text.replace(`{${key}}`, value);
  }
  return text;
}

/**
 * Execute a command on the UASC executor service.
 */
export async function executeOnUASC(request: ExecutionRequest): Promise<BridgeResult> {
  const body = JSON.stringify({ cmd: request.cmd, ...request.inputs });
  const timestamp = String(Math.floor(Date.now() / 1000));
  const signature = await computeSignature(UASC_SECRET, timestamp, body);

  try {
    const response = await fetch(`${UASC_URL}/exec`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-UASC-Client': UASC_CLIENT_ID,
        'X-UASC-Timestamp': timestamp,
        'X-UASC-Signature': signature,
      },
      body,
    });

    const data: ExecutionResponse = await response.json();

    return {
      executed: true,
      run_id: data.run_id,
      status: data.status === 'success' ? 'success' : 'failed',
      error: data.error || null,
      duration_ms: data.duration_ms,
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      executed: false,
      run_id: null,
      status: 'failed',
      error: `UASC executor unreachable: ${message}`,
      duration_ms: 0,
    };
  }
}

/**
 * Full bridge flow: take a confirmed PendingAction, execute it, return result.
 */
export async function bridgeAction(
  action: PendingActionData,
  context?: { task_title?: string; draft_data?: DraftData }
): Promise<BridgeResult> {
  const request = buildExecutionRequest(action, context);

  if (!request) {
    return {
      executed: false,
      run_id: null,
      status: 'skipped',
      error: null,
      duration_ms: 0,
    };
  }

  return executeOnUASC(request);
}

/**
 * Check if the UASC executor service is reachable.
 */
export async function checkExecutorHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${UASC_URL}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Get the token that would be used for a given action type.
 */
export function getTokenForAction(actionType: ActionType): string | null {
  return ACTION_TOKEN_MAP[actionType];
}
