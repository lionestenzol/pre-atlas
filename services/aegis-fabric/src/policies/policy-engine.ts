/**
 * Aegis Enterprise Fabric — Policy Engine
 *
 * JSON-based declarative policy evaluator.
 * Evaluates conditions against context, caches decisions, supports simulation.
 */

import {
  UUID, PolicyRule, PolicyCondition, PolicyOperator,
  PolicyEffect, PolicyDecision, PolicyEvaluationContext,
  AgentActionName, Mode, TenantTier, AgentProvider,
} from '../core/types.js';
import { generateUUID, now } from '../core/delta.js';
import { PolicyStore } from './policy-store.js';
import { DecisionCache } from './decision-cache.js';

const DEFAULT_CACHE_TTL = 60_000;  // 60 seconds

export class PolicyEngine {
  private policyStore: PolicyStore;
  private cache: DecisionCache;

  constructor(policyStore: PolicyStore, cache?: DecisionCache) {
    this.policyStore = policyStore;
    this.cache = cache || new DecisionCache(DEFAULT_CACHE_TTL);
  }

  /**
   * Evaluate policy for an agent action. Returns allow/deny/require_human.
   */
  evaluate(context: PolicyEvaluationContext): PolicyDecision {
    // Check cache first
    const cached = this.cache.get(
      context.tenant.id, context.agent.id, context.action, context.mode
    );
    if (cached) return cached;

    // Get rules for tenant, sorted by priority
    const rules = this.policyStore.getRules(context.tenant.id);

    // Evaluate rules in priority order (first match wins)
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

    // Default: ALLOW (permissive prototype default)
    const defaultDecision = this.buildDecision(context, 'ALLOW', null);
    this.cache.set(
      context.tenant.id, context.agent.id, context.action, context.mode,
      defaultDecision, DEFAULT_CACHE_TTL
    );
    return defaultDecision;
  }

  /**
   * Simulate policy evaluation without caching or side effects.
   */
  simulate(context: PolicyEvaluationContext): {
    decision: PolicyDecision;
    evaluated_rules: Array<{ rule: PolicyRule; matched: boolean }>;
  } {
    const rules = this.policyStore.getRules(context.tenant.id);
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
    // All conditions must match (AND logic)
    return rule.conditions.every(cond => this.evaluateCondition(cond, context));
  }

  private evaluateCondition(cond: PolicyCondition, context: PolicyEvaluationContext): boolean {
    const fieldValue = this.resolveField(cond.field, context);
    return this.applyOperator(cond.operator, fieldValue, cond.value);
  }

  /**
   * Resolve a dot-path field from the evaluation context.
   * Supported paths: tenant.tier, tenant.mode, agent.provider, agent.capabilities,
   * action, mode, params.*
   */
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
