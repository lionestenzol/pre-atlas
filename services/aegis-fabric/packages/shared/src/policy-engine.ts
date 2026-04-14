/**
 * Aegis Delta Fabric — Shared Policy Engine
 *
 * JSON-based declarative policy evaluator used by both Gateway (pre-check)
 * and Kernel (post-check). Evaluates conditions against context, supports
 * caching and simulation.
 */

import type {
  UUID, PolicyRule, PolicyCondition, PolicyOperator,
  PolicyEffect, PolicyDecision, PolicyEvaluationContext,
  AgentActionName, Mode,
} from './types.js';
import { generateUUID, now } from './hash.js';

const DEFAULT_CACHE_TTL = 60_000; // 60 seconds

// === DECISION CACHE ===

interface CacheEntry {
  decision: PolicyDecision;
  expiresAt: number;
}

export class DecisionCache {
  private cache: Map<string, CacheEntry> = new Map();
  private defaultTtlMs: number;

  constructor(defaultTtlMs: number = 60_000) {
    this.defaultTtlMs = defaultTtlMs;
  }

  private key(tenantId: UUID, agentId: UUID, action: AgentActionName, mode: Mode): string {
    return `${tenantId}:${agentId}:${action}:${mode}`;
  }

  get(tenantId: UUID, agentId: UUID, action: AgentActionName, mode: Mode): PolicyDecision | null {
    const k = this.key(tenantId, agentId, action, mode);
    const entry = this.cache.get(k);
    if (!entry) return null;

    if (Date.now() > entry.expiresAt) {
      this.cache.delete(k);
      return null;
    }

    return { ...entry.decision, cached: true };
  }

  set(tenantId: UUID, agentId: UUID, action: AgentActionName, mode: Mode, decision: PolicyDecision, ttlMs?: number): void {
    const k = this.key(tenantId, agentId, action, mode);
    this.cache.set(k, {
      decision,
      expiresAt: Date.now() + (ttlMs || this.defaultTtlMs),
    });
  }

  invalidateTenant(tenantId: UUID): void {
    for (const [key] of this.cache) {
      if (key.startsWith(tenantId + ':')) {
        this.cache.delete(key);
      }
    }
  }

  clear(): void {
    this.cache.clear();
  }

  size(): number {
    return this.cache.size;
  }
}

// === RULE PROVIDER INTERFACE ===

/**
 * Interface for providing policy rules to the engine.
 * Gateway implements this by fetching from Kernel; Kernel implements via direct DB query.
 */
export interface PolicyRuleProvider {
  getRules(tenantId: UUID): PolicyRule[];
}

// === POLICY ENGINE ===

export class PolicyEngine {
  private ruleProvider: PolicyRuleProvider;
  private cache: DecisionCache;

  constructor(ruleProvider: PolicyRuleProvider, cache?: DecisionCache) {
    this.ruleProvider = ruleProvider;
    this.cache = cache || new DecisionCache(DEFAULT_CACHE_TTL);
  }

  /**
   * Evaluate policy for an agent action. Returns allow/deny/require_human.
   */
  evaluate(context: PolicyEvaluationContext): PolicyDecision {
    const cached = this.cache.get(
      context.tenant.id, context.agent.id, context.action, context.mode
    );
    if (cached) return cached;

    const rules = this.ruleProvider.getRules(context.tenant.id);

    for (const rule of rules) {
      if (this.evaluateRule(rule, context)) {
        const decision = this.buildDecision(context, rule.effect, rule);
        this.cache.set(
          context.tenant.id, context.agent.id, context.action, context.mode,
          decision, DEFAULT_CACHE_TTL
        );
        return decision;
      }
    }

    const defaultDecision = this.buildDecision(context, 'ALLOW', null);
    this.cache.set(
      context.tenant.id, context.agent.id, context.action, context.mode,
      defaultDecision, DEFAULT_CACHE_TTL
    );
    return defaultDecision;
  }

  /**
   * Simulate policy evaluation without caching.
   */
  simulate(context: PolicyEvaluationContext): {
    decision: PolicyDecision;
    evaluated_rules: Array<{ rule: PolicyRule; matched: boolean }>;
  } {
    const rules = this.ruleProvider.getRules(context.tenant.id);
    const evaluated: Array<{ rule: PolicyRule; matched: boolean }> = [];
    let matchedRule: PolicyRule | null = null;

    for (const rule of rules) {
      const matched = this.evaluateRule(rule, context);
      evaluated.push({ rule, matched });
      if (matched && !matchedRule) {
        matchedRule = rule;
      }
    }

    const effect: PolicyEffect = matchedRule ? matchedRule.effect : 'ALLOW';
    const decision = this.buildDecision(context, effect, matchedRule);

    return { decision, evaluated_rules: evaluated };
  }

  invalidateCache(tenantId: UUID): void {
    this.cache.invalidateTenant(tenantId);
  }

  // === PRIVATE ===

  private evaluateRule(rule: PolicyRule, context: PolicyEvaluationContext): boolean {
    return rule.conditions.every(cond => this.evaluateCondition(cond, context));
  }

  private evaluateCondition(cond: PolicyCondition, context: PolicyEvaluationContext): boolean {
    const fieldValue = this.resolveField(cond.field, context);
    return this.applyOperator(cond.operator, fieldValue, cond.value);
  }

  private resolveField(field: string, context: PolicyEvaluationContext): unknown {
    const parts = field.split('.');
    let current: unknown = context;

    for (const part of parts) {
      if (current === null || current === undefined) return undefined;
      if (typeof current !== 'object') return undefined;
      current = (current as Record<string, unknown>)[part];
    }

    return current;
  }

  private applyOperator(operator: PolicyOperator, fieldValue: unknown, condValue: unknown): boolean {
    switch (operator) {
      case 'eq':
        return fieldValue === condValue;
      case 'neq':
        return fieldValue !== condValue;
      case 'in':
        if (!Array.isArray(condValue)) return false;
        return condValue.includes(fieldValue);
      case 'not_in':
        if (!Array.isArray(condValue)) return true;
        return !condValue.includes(fieldValue);
      case 'gt':
        return typeof fieldValue === 'number' && typeof condValue === 'number' && fieldValue > condValue;
      case 'lt':
        return typeof fieldValue === 'number' && typeof condValue === 'number' && fieldValue < condValue;
      case 'gte':
        return typeof fieldValue === 'number' && typeof condValue === 'number' && fieldValue >= condValue;
      case 'lte':
        return typeof fieldValue === 'number' && typeof condValue === 'number' && fieldValue <= condValue;
      case 'exists':
        return condValue ? fieldValue !== undefined && fieldValue !== null : fieldValue === undefined || fieldValue === null;
      default:
        return false;
    }
  }

  private buildDecision(
    context: PolicyEvaluationContext,
    effect: PolicyEffect,
    matchedRule: PolicyRule | null
  ): PolicyDecision {
    return {
      decision_id: generateUUID(),
      tenant_id: context.tenant.id,
      agent_id: context.agent.id,
      action: context.action,
      effect,
      matched_rule_id: matchedRule?.rule_id || null,
      reason: matchedRule?.reason || 'Default allow (no matching rule)',
      context: {
        mode: context.mode,
        tenant_tier: context.tenant.tier,
        agent_provider: context.agent.provider,
      },
      cached: false,
      evaluated_at: now(),
      cache_ttl_ms: DEFAULT_CACHE_TTL,
    };
  }
}
