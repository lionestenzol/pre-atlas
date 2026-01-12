/**
 * Delta-State Fabric — Module 5: AI Design Layer (Compiler Brain)
 *
 * Uses LLMs to DESIGN new structure, then compiles that structure into
 * deterministic LUTs, templates, and routing rules.
 *
 * Laws:
 * - AI may NEVER execute runtime actions
 * - AI only produces DesignProposal entities
 * - All outputs require human review before compilation
 * - Compilation produces deterministic LUT updates only
 */

import {
  UUID,
  Timestamp,
  SHA256,
  Mode,
  Entity,
  Delta,
  AIRole,
  DesignProposalData,
  DesignProposalType,
  DesignStructure,
  NewTemplateStructure,
  RoutingPatchStructure,
  RoutingConditionPatch,
  WorkflowSuggestionStructure,
  WorkflowAction,
  AutomationRuleStructure,
  DictionarySeedStructure,
  DictionarySeedEntry,
  DiscoveryProposalData,
  TemplateSuggestionStructure,
  RoutingSuggestionStructure,
  PatternPromotionStructure,
  MotifPromotionStructure,
  DraftData,
  TaskData,
  ProjectData,
  SystemStateData,
  Template,
  TokenData,
  PatternData,
  MotifData,
  JsonPatch,
} from './types';
import { createEntity, createDelta, now, hashState, generateUUID } from './delta';
import { LeverageMove } from './preparation';

// === CONSTANTS ===

const MAX_PROPOSALS_PER_ROLE = 5;
const MIN_CONFIDENCE_THRESHOLD = 0.6;

// === LLM ABSTRACTION ===

/**
 * LLM Request/Response abstraction.
 * In production, this would call actual LLM APIs.
 * For v0, we use deterministic rule-based logic to simulate LLM behavior.
 */
export interface LLMRequest {
  role: AIRole;
  prompt: string;
  context: Record<string, unknown>;
  max_tokens?: number;
}

export interface LLMResponse {
  role: AIRole;
  content: string;
  structured_output: unknown;
  confidence: number;
}

/**
 * Simulated LLM call - deterministic for v0.
 * Replace with actual LLM integration in production.
 */
export async function callLLM(request: LLMRequest): Promise<LLMResponse> {
  // v0: Return deterministic responses based on role and context
  // This maintains the architecture while allowing future LLM integration
  return {
    role: request.role,
    content: `[${request.role}] Analyzed context and produced structured output`,
    structured_output: request.context,
    confidence: 0.75,
  };
}

// === FINGERPRINT CALCULATION ===

export async function calculateDesignFingerprint(
  proposalType: DesignProposalType,
  structure: DesignStructure,
  sourceDiscoveryIds: UUID[]
): Promise<SHA256> {
  return hashState({
    proposal_type: proposalType,
    structure_hash: await hashState(structure),
    source_ids: [...sourceDiscoveryIds].sort(),
  });
}

// === INPUT FEEDS ===

export interface DesignInputFeeds {
  // From Module 4
  discoveryProposals: Array<{ entity: Entity; state: DiscoveryProposalData }>;
  // Operational context
  drafts: Array<{ entity: Entity; state: DraftData }>;
  tasks: Array<{ entity: Entity; state: TaskData }>;
  projects: Array<{ entity: Entity; state: ProjectData }>;
  systemState: { entity: Entity; state: SystemStateData };
  // LUT context
  existingTemplates: Template[];
  leverageMoves: LeverageMove[];
  // Dictionary context
  tokens: Array<{ entity: Entity; state: TokenData }>;
  patterns: Array<{ entity: Entity; state: PatternData }>;
  motifs: Array<{ entity: Entity; state: MotifData }>;
  // Routing history
  routingTransitions: Array<{ from: Mode; to: Mode; count: number }>;
  // Existing proposals (for dedup)
  existingDesignProposals: Array<{ entity: Entity; state: DesignProposalData }>;
}

// === ROLE 1: LINGUIST — Template Design ===

export interface LinguistOutput {
  proposals: Array<{ entity: Entity; delta: Delta; state: DesignProposalData }>;
}

export async function runLinguistRole(
  feeds: DesignInputFeeds,
  existingFingerprints: Set<string>
): Promise<LinguistOutput> {
  const proposals: Array<{ entity: Entity; delta: Delta; state: DesignProposalData }> = [];

  // Find TEMPLATE_SUGGESTION discoveries to process
  const templateSuggestions = feeds.discoveryProposals.filter(
    (d) =>
      d.state.proposal_type === 'TEMPLATE_SUGGESTION' &&
      d.state.status === 'ACCEPTED'
  );

  for (const discovery of templateSuggestions.slice(0, MAX_PROPOSALS_PER_ROLE)) {
    const suggestionStructure = discovery.state.proposed_structure as TemplateSuggestionStructure;

    // Check if template already exists
    const exists = feeds.existingTemplates.some(
      (t) => t.template_id === suggestionStructure.suggested_template_id
    );
    if (exists) continue;

    // Design the template
    const designedTemplate = await designTemplate(suggestionStructure, feeds);

    const fingerprint = await calculateDesignFingerprint(
      'NEW_TEMPLATE',
      designedTemplate,
      [discovery.entity.entity_id]
    );

    if (existingFingerprints.has(fingerprint)) continue;

    const proposalData: DesignProposalData = {
      proposal_type: 'NEW_TEMPLATE',
      description: `New template "${designedTemplate.template_id}" with ${designedTemplate.slots.length} slots`,
      proposed_structure: designedTemplate,
      source_discovery_ids: [discovery.entity.entity_id],
      confidence: discovery.state.confidence * 0.9, // Slight confidence reduction
      fingerprint,
      status: 'NEW',
      designed_by: 'linguist',
      created_at: now(),
      reviewed_at: null,
      review_notes: null,
      compiled_at: null,
    };

    const result = await createEntity('design_proposal', proposalData);
    proposals.push(result);
    existingFingerprints.add(fingerprint);
  }

  // Also analyze draft patterns for new template opportunities
  const draftPatterns = analyzeDraftPatterns(feeds.drafts);
  for (const pattern of draftPatterns.slice(0, MAX_PROPOSALS_PER_ROLE - proposals.length)) {
    if (pattern.frequency < 3) continue;

    const designedTemplate: NewTemplateStructure = {
      type: 'NEW_TEMPLATE',
      template_id: `DERIVED_${generateUUID().slice(0, 8).toUpperCase()}`,
      pattern: pattern.pattern,
      slots: pattern.slots,
      mode_restriction: pattern.primaryMode,
      example_renderings: pattern.examples,
    };

    const fingerprint = await calculateDesignFingerprint(
      'NEW_TEMPLATE',
      designedTemplate,
      pattern.sourceEntityIds
    );

    if (existingFingerprints.has(fingerprint)) continue;

    const proposalData: DesignProposalData = {
      proposal_type: 'NEW_TEMPLATE',
      description: `Derived template from ${pattern.frequency} similar drafts`,
      proposed_structure: designedTemplate,
      source_discovery_ids: pattern.sourceEntityIds,
      confidence: Math.min(pattern.frequency / 10, 0.9),
      fingerprint,
      status: 'NEW',
      designed_by: 'linguist',
      created_at: now(),
      reviewed_at: null,
      review_notes: null,
      compiled_at: null,
    };

    const result = await createEntity('design_proposal', proposalData);
    proposals.push(result);
    existingFingerprints.add(fingerprint);
  }

  return { proposals };
}

async function designTemplate(
  suggestion: TemplateSuggestionStructure,
  feeds: DesignInputFeeds
): Promise<NewTemplateStructure> {
  // Refine the template based on existing patterns
  const refinedSlots = suggestion.slots.map((slot, i) => {
    // Standardize slot names
    if (slot.includes('slot_')) {
      return `param_${i + 1}`;
    }
    return slot;
  });

  // Generate example renderings
  const examples = refinedSlots.length > 0
    ? [
        suggestion.pattern.replace(/\{[^}]+\}/g, '[value]'),
        suggestion.pattern,
      ]
    : [suggestion.pattern];

  return {
    type: 'NEW_TEMPLATE',
    template_id: suggestion.suggested_template_id,
    pattern: suggestion.pattern,
    slots: refinedSlots,
    mode_restriction: suggestion.mode_restriction,
    example_renderings: examples,
  };
}

interface DraftPattern {
  pattern: string;
  slots: string[];
  frequency: number;
  primaryMode: Mode | null;
  examples: string[];
  sourceEntityIds: UUID[];
}

function analyzeDraftPatterns(
  drafts: Array<{ entity: Entity; state: DraftData }>
): DraftPattern[] {
  const patternMap = new Map<string, DraftPattern>();

  for (const draft of drafts) {
    const templateKey = draft.state.template_id;
    const existing = patternMap.get(templateKey);

    if (existing) {
      existing.frequency++;
      existing.sourceEntityIds.push(draft.entity.entity_id);
      if (existing.examples.length < 3) {
        existing.examples.push(
          `${draft.state.template_id}: ${JSON.stringify(draft.state.params)}`
        );
      }
    } else {
      patternMap.set(templateKey, {
        pattern: draft.state.template_id,
        slots: Object.keys(draft.state.params),
        frequency: 1,
        primaryMode: draft.state.mode_context,
        examples: [`${draft.state.template_id}: ${JSON.stringify(draft.state.params)}`],
        sourceEntityIds: [draft.entity.entity_id],
      });
    }
  }

  return Array.from(patternMap.values())
    .filter((p) => p.frequency >= 2)
    .sort((a, b) => b.frequency - a.frequency);
}

// === ROLE 2: ARCHITECT — Routing Patches ===

export interface ArchitectOutput {
  proposals: Array<{ entity: Entity; delta: Delta; state: DesignProposalData }>;
}

export async function runArchitectRole(
  feeds: DesignInputFeeds,
  existingFingerprints: Set<string>
): Promise<ArchitectOutput> {
  const proposals: Array<{ entity: Entity; delta: Delta; state: DesignProposalData }> = [];

  // Find ROUTING_SUGGESTION discoveries to process
  const routingSuggestions = feeds.discoveryProposals.filter(
    (d) =>
      d.state.proposal_type === 'ROUTING_SUGGESTION' &&
      d.state.status === 'ACCEPTED'
  );

  for (const discovery of routingSuggestions.slice(0, MAX_PROPOSALS_PER_ROLE)) {
    const suggestionStructure = discovery.state.proposed_structure as RoutingSuggestionStructure;

    // Design routing patch based on issue type
    const routingPatch = await designRoutingPatch(suggestionStructure, feeds);
    if (!routingPatch) continue;

    const fingerprint = await calculateDesignFingerprint(
      'ROUTING_PATCH',
      routingPatch,
      [discovery.entity.entity_id]
    );

    if (existingFingerprints.has(fingerprint)) continue;

    const proposalData: DesignProposalData = {
      proposal_type: 'ROUTING_PATCH',
      description: `Routing fix for ${suggestionStructure.issue_type} affecting ${suggestionStructure.affected_modes.join(', ')}`,
      proposed_structure: routingPatch,
      source_discovery_ids: [discovery.entity.entity_id],
      confidence: discovery.state.confidence * 0.85,
      fingerprint,
      status: 'NEW',
      designed_by: 'architect',
      created_at: now(),
      reviewed_at: null,
      review_notes: null,
      compiled_at: null,
    };

    const result = await createEntity('design_proposal', proposalData);
    proposals.push(result);
    existingFingerprints.add(fingerprint);
  }

  // Analyze routing transitions for optimization opportunities
  const optimizations = analyzeRoutingOptimizations(feeds.routingTransitions, feeds.systemState.state);
  for (const opt of optimizations.slice(0, MAX_PROPOSALS_PER_ROLE - proposals.length)) {
    const fingerprint = await calculateDesignFingerprint(
      'ROUTING_PATCH',
      opt.patch,
      []
    );

    if (existingFingerprints.has(fingerprint)) continue;

    const proposalData: DesignProposalData = {
      proposal_type: 'ROUTING_PATCH',
      description: opt.description,
      proposed_structure: opt.patch,
      source_discovery_ids: [],
      confidence: opt.confidence,
      fingerprint,
      status: 'NEW',
      designed_by: 'architect',
      created_at: now(),
      reviewed_at: null,
      review_notes: null,
      compiled_at: null,
    };

    const result = await createEntity('design_proposal', proposalData);
    proposals.push(result);
    existingFingerprints.add(fingerprint);
  }

  return { proposals };
}

async function designRoutingPatch(
  suggestion: RoutingSuggestionStructure,
  feeds: DesignInputFeeds
): Promise<RoutingPatchStructure | null> {
  const changes: RoutingConditionPatch[] = [];

  switch (suggestion.issue_type) {
    case 'LOOP_DETECTED':
      // Suggest widening the gap between modes
      if (suggestion.affected_modes.length >= 2) {
        changes.push({
          signal: 'open_loops',
          current_threshold: '≤1 for HIGH',
          proposed_threshold: '≤0 for HIGH',
          effect: 'Stricter exit condition to prevent oscillation',
        });
      }
      break;

    case 'SKIP_DETECTED':
      // Suggest adding intermediate checks
      changes.push({
        signal: 'assets_shipped',
        current_threshold: '≥1 for OK',
        proposed_threshold: '≥1 for OK, require sleep OK',
        effect: 'Add prerequisite check before mode skip',
      });
      break;

    case 'STUCK_MODE':
      // Suggest relaxing exit conditions
      const stuckMode = suggestion.affected_modes[0];
      if (stuckMode === 'RECOVER') {
        changes.push({
          signal: 'sleep_hours',
          current_threshold: '≥6 for OK',
          proposed_threshold: '≥5.5 for OK',
          effect: 'Slightly relaxed recovery threshold',
        });
      }
      break;

    case 'DRIFT':
      // General stabilization
      changes.push({
        signal: 'deep_work_blocks',
        current_threshold: '≥2 for HIGH',
        proposed_threshold: '≥2 for HIGH, sticky for 24h',
        effect: 'Add temporal smoothing to prevent drift',
      });
      break;

    default:
      return null;
  }

  if (changes.length === 0) return null;

  return {
    type: 'ROUTING_PATCH',
    target_mode: suggestion.affected_modes[0],
    condition_changes: changes,
    rationale: suggestion.suggested_fix,
  };
}

interface RoutingOptimization {
  patch: RoutingPatchStructure;
  description: string;
  confidence: number;
}

function analyzeRoutingOptimizations(
  transitions: Array<{ from: Mode; to: Mode; count: number }>,
  currentState: SystemStateData
): RoutingOptimization[] {
  const optimizations: RoutingOptimization[] = [];

  // Find rarely used transitions that might need adjustment
  const totalTransitions = transitions.reduce((sum, t) => sum + t.count, 0);
  if (totalTransitions < 10) return optimizations; // Not enough data

  // Check for unbalanced mode usage
  const modeCounts = new Map<Mode, number>();
  for (const t of transitions) {
    modeCounts.set(t.to, (modeCounts.get(t.to) || 0) + t.count);
  }

  // If BUILD mode is rarely reached, suggest easing CLOSE_LOOPS exit
  const buildCount = modeCounts.get('BUILD') || 0;
  if (buildCount < totalTransitions * 0.1) {
    optimizations.push({
      patch: {
        type: 'ROUTING_PATCH',
        target_mode: 'CLOSE_LOOPS',
        condition_changes: [{
          signal: 'open_loops',
          current_threshold: '≤1 for HIGH',
          proposed_threshold: '≤2 for HIGH',
          effect: 'Easier progression to BUILD mode',
        }],
        rationale: 'BUILD mode is underutilized; relaxing CLOSE_LOOPS exit',
      },
      description: 'Optimize CLOSE_LOOPS→BUILD transition (BUILD underutilized)',
      confidence: 0.7,
    });
  }

  return optimizations;
}

// === ROLE 3: AUTOMATOR — Workflow Rules ===

export interface AutomatorOutput {
  proposals: Array<{ entity: Entity; delta: Delta; state: DesignProposalData }>;
}

export async function runAutomatorRole(
  feeds: DesignInputFeeds,
  existingFingerprints: Set<string>
): Promise<AutomatorOutput> {
  const proposals: Array<{ entity: Entity; delta: Delta; state: DesignProposalData }> = [];

  // Analyze task patterns for workflow suggestions
  const workflowPatterns = analyzeTaskWorkflows(feeds.tasks, feeds.projects);

  for (const pattern of workflowPatterns.slice(0, MAX_PROPOSALS_PER_ROLE)) {
    const workflowSuggestion: WorkflowSuggestionStructure = {
      type: 'WORKFLOW_SUGGESTION',
      trigger_conditions: pattern.triggers,
      actions: pattern.actions,
      mode_applicability: pattern.modes,
    };

    const fingerprint = await calculateDesignFingerprint(
      'WORKFLOW_SUGGESTION',
      workflowSuggestion,
      pattern.sourceEntityIds
    );

    if (existingFingerprints.has(fingerprint)) continue;

    const proposalData: DesignProposalData = {
      proposal_type: 'WORKFLOW_SUGGESTION',
      description: pattern.description,
      proposed_structure: workflowSuggestion,
      source_discovery_ids: pattern.sourceEntityIds,
      confidence: pattern.confidence,
      fingerprint,
      status: 'NEW',
      designed_by: 'automator',
      created_at: now(),
      reviewed_at: null,
      review_notes: null,
      compiled_at: null,
    };

    const result = await createEntity('design_proposal', proposalData);
    proposals.push(result);
    existingFingerprints.add(fingerprint);
  }

  // Analyze leverage moves for automation rules
  const automationRules = deriveAutomationRules(feeds.leverageMoves, feeds.drafts);

  for (const rule of automationRules.slice(0, MAX_PROPOSALS_PER_ROLE - proposals.length)) {
    const fingerprint = await calculateDesignFingerprint(
      'AUTOMATION_RULE',
      rule.structure,
      []
    );

    if (existingFingerprints.has(fingerprint)) continue;

    const proposalData: DesignProposalData = {
      proposal_type: 'AUTOMATION_RULE',
      description: rule.description,
      proposed_structure: rule.structure,
      source_discovery_ids: [],
      confidence: rule.confidence,
      fingerprint,
      status: 'NEW',
      designed_by: 'automator',
      created_at: now(),
      reviewed_at: null,
      review_notes: null,
      compiled_at: null,
    };

    const result = await createEntity('design_proposal', proposalData);
    proposals.push(result);
    existingFingerprints.add(fingerprint);
  }

  return { proposals };
}

interface WorkflowPattern {
  triggers: Record<string, string>;
  actions: WorkflowAction[];
  modes: Mode[];
  description: string;
  confidence: number;
  sourceEntityIds: UUID[];
}

function analyzeTaskWorkflows(
  tasks: Array<{ entity: Entity; state: TaskData }>,
  projects: Array<{ entity: Entity; state: ProjectData }>
): WorkflowPattern[] {
  const patterns: WorkflowPattern[] = [];

  // Pattern: Multiple BLOCKED tasks → suggest batch unblock workflow
  const blockedTasks = tasks.filter((t) => t.state.status === 'BLOCKED');
  if (blockedTasks.length >= 3) {
    patterns.push({
      triggers: { task_status: 'BLOCKED', count: '≥3' },
      actions: [
        { action_type: 'create_draft', parameters: { draft_type: 'PLAN', template: 'BATCH_UNBLOCK' } },
        { action_type: 'flag_priority', parameters: { level: 'HIGH' } },
      ],
      modes: ['CLOSE_LOOPS'],
      description: `Batch unblock workflow for ${blockedTasks.length} blocked tasks`,
      confidence: 0.75,
      sourceEntityIds: blockedTasks.slice(0, 5).map((t) => t.entity.entity_id),
    });
  }

  // Pattern: Overdue tasks → escalation workflow
  const now_ts = now();
  const overdueTasks = tasks.filter(
    (t) => t.state.status === 'OPEN' && t.state.due_at && t.state.due_at < now_ts
  );
  if (overdueTasks.length >= 2) {
    patterns.push({
      triggers: { task_overdue: 'true' },
      actions: [
        { action_type: 'flag_priority', parameters: { level: 'HIGH' } },
        { action_type: 'schedule_review', parameters: { window: '24h' } },
      ],
      modes: ['CLOSE_LOOPS', 'BUILD'],
      description: `Escalation workflow for ${overdueTasks.length} overdue tasks`,
      confidence: 0.8,
      sourceEntityIds: overdueTasks.slice(0, 5).map((t) => t.entity.entity_id),
    });
  }

  // Pattern: Project with all tasks done → completion workflow
  for (const project of projects) {
    if (project.state.status !== 'ACTIVE') continue;

    const projectTasks = tasks.filter((t) =>
      project.state.task_ids.includes(t.entity.entity_id)
    );
    const allDone = projectTasks.length > 0 &&
      projectTasks.every((t) => t.state.status === 'DONE');

    if (allDone) {
      patterns.push({
        triggers: { project_tasks_complete: 'true' },
        actions: [
          { action_type: 'create_draft', parameters: { draft_type: 'ASSET', template: 'PROJECT_COMPLETE' } },
          { action_type: 'suggest_template', parameters: { template: 'CLOSE' } },
        ],
        modes: ['BUILD', 'COMPOUND'],
        description: `Project completion workflow for "${project.state.name_template}"`,
        confidence: 0.85,
        sourceEntityIds: [project.entity.entity_id],
      });
    }
  }

  return patterns;
}

interface DerivedAutomationRule {
  structure: AutomationRuleStructure;
  description: string;
  confidence: number;
}

function deriveAutomationRules(
  leverageMoves: LeverageMove[],
  drafts: Array<{ entity: Entity; state: DraftData }>
): DerivedAutomationRule[] {
  const rules: DerivedAutomationRule[] = [];

  // Derive rules from frequently used leverage moves
  const moveUsage = new Map<string, number>();
  for (const move of leverageMoves) {
    moveUsage.set(move.move_id, (moveUsage.get(move.move_id) || 0) + 1);
  }

  for (const [moveId, count] of moveUsage) {
    if (count < 3) continue;

    const move = leverageMoves.find((m) => m.move_id === moveId);
    if (!move) continue;

    rules.push({
      structure: {
        type: 'AUTOMATION_RULE',
        rule_id: `auto_${moveId}`,
        trigger_entity_type: 'system_state',
        trigger_conditions: move.trigger_conditions,
        derived_action_type: 'create_asset',
        action_template: {
          suggested_actions: move.recommended_next_actions,
          mode: move.mode,
        },
      },
      description: `Auto-suggest "${move.title}" when conditions match`,
      confidence: Math.min(count / 10, 0.8),
    });
  }

  return rules;
}

// === ROLE 4: SYNTHESIZER — Dictionary Seeds ===

export interface SynthesizerOutput {
  proposals: Array<{ entity: Entity; delta: Delta; state: DesignProposalData }>;
}

export async function runSynthesizerRole(
  feeds: DesignInputFeeds,
  existingFingerprints: Set<string>
): Promise<SynthesizerOutput> {
  const proposals: Array<{ entity: Entity; delta: Delta; state: DesignProposalData }> = [];

  // Process PATTERN_PROMOTION discoveries
  const patternPromotions = feeds.discoveryProposals.filter(
    (d) =>
      d.state.proposal_type === 'PATTERN_PROMOTION' &&
      d.state.status === 'ACCEPTED'
  );

  for (const discovery of patternPromotions.slice(0, MAX_PROPOSALS_PER_ROLE)) {
    const promotionStructure = discovery.state.proposed_structure as PatternPromotionStructure;

    // Check if pattern already exists
    const exists = feeds.patterns.some(
      (p) => p.state.pattern_id === promotionStructure.suggested_pattern_id
    );
    if (exists) continue;

    const dictionarySeed: DictionarySeedStructure = {
      type: 'DICTIONARY_SEED',
      seed_type: 'pattern',
      proposed_entries: [{
        id: promotionStructure.suggested_pattern_id,
        value: promotionStructure.token_sequence,
        source_examples: promotionStructure.example_texts,
      }],
    };

    const fingerprint = await calculateDesignFingerprint(
      'DICTIONARY_SEED',
      dictionarySeed,
      [discovery.entity.entity_id]
    );

    if (existingFingerprints.has(fingerprint)) continue;

    const proposalData: DesignProposalData = {
      proposal_type: 'DICTIONARY_SEED',
      description: `Pattern seed: "${promotionStructure.suggested_pattern_id}"`,
      proposed_structure: dictionarySeed,
      source_discovery_ids: [discovery.entity.entity_id],
      confidence: discovery.state.confidence,
      fingerprint,
      status: 'NEW',
      designed_by: 'synthesizer',
      created_at: now(),
      reviewed_at: null,
      review_notes: null,
      compiled_at: null,
    };

    const result = await createEntity('design_proposal', proposalData);
    proposals.push(result);
    existingFingerprints.add(fingerprint);
  }

  // Process MOTIF_PROMOTION discoveries
  const motifPromotions = feeds.discoveryProposals.filter(
    (d) =>
      d.state.proposal_type === 'MOTIF_PROMOTION' &&
      d.state.status === 'ACCEPTED'
  );

  for (const discovery of motifPromotions.slice(0, MAX_PROPOSALS_PER_ROLE - proposals.length)) {
    const promotionStructure = discovery.state.proposed_structure as MotifPromotionStructure;

    // Check if motif already exists
    const exists = feeds.motifs.some(
      (m) => m.state.motif_id === promotionStructure.suggested_motif_id
    );
    if (exists) continue;

    const dictionarySeed: DictionarySeedStructure = {
      type: 'DICTIONARY_SEED',
      seed_type: 'motif',
      proposed_entries: [{
        id: promotionStructure.suggested_motif_id,
        value: promotionStructure.pattern_sequence,
        slots: promotionStructure.slots,
        source_examples: [],
      }],
    };

    const fingerprint = await calculateDesignFingerprint(
      'DICTIONARY_SEED',
      dictionarySeed,
      [discovery.entity.entity_id]
    );

    if (existingFingerprints.has(fingerprint)) continue;

    const proposalData: DesignProposalData = {
      proposal_type: 'DICTIONARY_SEED',
      description: `Motif seed: "${promotionStructure.suggested_motif_id}" with ${promotionStructure.slots.length} slots`,
      proposed_structure: dictionarySeed,
      source_discovery_ids: [discovery.entity.entity_id],
      confidence: discovery.state.confidence,
      fingerprint,
      status: 'NEW',
      designed_by: 'synthesizer',
      created_at: now(),
      reviewed_at: null,
      review_notes: null,
      compiled_at: null,
    };

    const result = await createEntity('design_proposal', proposalData);
    proposals.push(result);
    existingFingerprints.add(fingerprint);
  }

  // Analyze token frequency for new token seeds
  const tokenSeeds = analyzeTokenOpportunities(feeds.tokens, feeds.drafts);
  for (const seed of tokenSeeds.slice(0, MAX_PROPOSALS_PER_ROLE - proposals.length)) {
    const fingerprint = await calculateDesignFingerprint(
      'DICTIONARY_SEED',
      seed.structure,
      seed.sourceEntityIds
    );

    if (existingFingerprints.has(fingerprint)) continue;

    const proposalData: DesignProposalData = {
      proposal_type: 'DICTIONARY_SEED',
      description: seed.description,
      proposed_structure: seed.structure,
      source_discovery_ids: seed.sourceEntityIds,
      confidence: seed.confidence,
      fingerprint,
      status: 'NEW',
      designed_by: 'synthesizer',
      created_at: now(),
      reviewed_at: null,
      review_notes: null,
      compiled_at: null,
    };

    const result = await createEntity('design_proposal', proposalData);
    proposals.push(result);
    existingFingerprints.add(fingerprint);
  }

  return { proposals };
}

interface TokenOpportunity {
  structure: DictionarySeedStructure;
  description: string;
  confidence: number;
  sourceEntityIds: UUID[];
}

function analyzeTokenOpportunities(
  existingTokens: Array<{ entity: Entity; state: TokenData }>,
  drafts: Array<{ entity: Entity; state: DraftData }>
): TokenOpportunity[] {
  const opportunities: TokenOpportunity[] = [];
  const existingValues = new Set(existingTokens.map((t) => t.state.value.toLowerCase()));

  // Count word frequencies across drafts
  const wordFrequency = new Map<string, { count: number; sources: UUID[] }>();

  for (const draft of drafts) {
    const words = Object.values(draft.state.params)
      .join(' ')
      .toLowerCase()
      .split(/\s+/)
      .filter((w) => w.length >= 4); // Only meaningful words

    for (const word of words) {
      if (existingValues.has(word)) continue;

      const existing = wordFrequency.get(word);
      if (existing) {
        existing.count++;
        if (!existing.sources.includes(draft.entity.entity_id)) {
          existing.sources.push(draft.entity.entity_id);
        }
      } else {
        wordFrequency.set(word, { count: 1, sources: [draft.entity.entity_id] });
      }
    }
  }

  // Create seeds for high-frequency words
  const highFrequencyWords = Array.from(wordFrequency.entries())
    .filter(([, data]) => data.count >= 5)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 5);

  if (highFrequencyWords.length > 0) {
    const entries: DictionarySeedEntry[] = highFrequencyWords.map(([word, data]) => ({
      id: `token_${word}`,
      value: word,
      source_examples: data.sources.slice(0, 3).map((id) => `Draft ${id.slice(0, 8)}`),
    }));

    opportunities.push({
      structure: {
        type: 'DICTIONARY_SEED',
        seed_type: 'token',
        proposed_entries: entries,
      },
      description: `${entries.length} high-frequency token seeds`,
      confidence: 0.7,
      sourceEntityIds: highFrequencyWords.flatMap(([, data]) => data.sources).slice(0, 10),
    });
  }

  return opportunities;
}

// === COMPILATION GATE ===

export interface CompilationResult {
  success: boolean;
  compiled_deltas: Delta[];
  target_lut: string;
  error?: string;
}

/**
 * Compile an accepted DesignProposal into LUT updates.
 * Returns deltas that update the appropriate lookup tables.
 */
export async function compileDesignProposal(
  proposal: { entity: Entity; state: DesignProposalData }
): Promise<CompilationResult> {
  if (proposal.state.status !== 'ACCEPTED') {
    return {
      success: false,
      compiled_deltas: [],
      target_lut: '',
      error: 'Proposal must be ACCEPTED before compilation',
    };
  }

  const structure = proposal.state.proposed_structure;

  switch (structure.type) {
    case 'NEW_TEMPLATE':
      return compileNewTemplate(structure, proposal);

    case 'ROUTING_PATCH':
      return compileRoutingPatch(structure, proposal);

    case 'WORKFLOW_SUGGESTION':
      return compileWorkflowSuggestion(structure, proposal);

    case 'AUTOMATION_RULE':
      return compileAutomationRule(structure, proposal);

    case 'DICTIONARY_SEED':
      return compileDictionarySeed(structure, proposal);

    default:
      return {
        success: false,
        compiled_deltas: [],
        target_lut: '',
        error: `Unknown structure type`,
      };
  }
}

async function compileNewTemplate(
  structure: NewTemplateStructure,
  proposal: { entity: Entity; state: DesignProposalData }
): Promise<CompilationResult> {
  // In production, this would update the template LUT
  // For v0, we return the delta that would be applied

  const templateEntry: Template = {
    template_id: structure.template_id,
    slots: structure.slots,
    pattern: structure.pattern,
  };

  // Mark proposal as compiled
  const compiledPatch: JsonPatch[] = [
    { op: 'replace', path: '/compiled_at', value: now() },
  ];

  const { delta } = await createDelta(
    proposal.entity,
    proposal.state,
    compiledPatch,
    'system'
  );

  return {
    success: true,
    compiled_deltas: [delta],
    target_lut: 'TEMPLATE_CATALOG',
  };
}

async function compileRoutingPatch(
  structure: RoutingPatchStructure,
  proposal: { entity: Entity; state: DesignProposalData }
): Promise<CompilationResult> {
  // Would update routing.ts MODE_TRANSITIONS LUT
  const compiledPatch: JsonPatch[] = [
    { op: 'replace', path: '/compiled_at', value: now() },
  ];

  const { delta } = await createDelta(
    proposal.entity,
    proposal.state,
    compiledPatch,
    'system'
  );

  return {
    success: true,
    compiled_deltas: [delta],
    target_lut: 'MODE_TRANSITIONS',
  };
}

async function compileWorkflowSuggestion(
  structure: WorkflowSuggestionStructure,
  proposal: { entity: Entity; state: DesignProposalData }
): Promise<CompilationResult> {
  // Would update preparation.ts workflow rules
  const compiledPatch: JsonPatch[] = [
    { op: 'replace', path: '/compiled_at', value: now() },
  ];

  const { delta } = await createDelta(
    proposal.entity,
    proposal.state,
    compiledPatch,
    'system'
  );

  return {
    success: true,
    compiled_deltas: [delta],
    target_lut: 'PREPARATION_WORKFLOWS',
  };
}

async function compileAutomationRule(
  structure: AutomationRuleStructure,
  proposal: { entity: Entity; state: DesignProposalData }
): Promise<CompilationResult> {
  // Would update pending action derivation rules
  const compiledPatch: JsonPatch[] = [
    { op: 'replace', path: '/compiled_at', value: now() },
  ];

  const { delta } = await createDelta(
    proposal.entity,
    proposal.state,
    compiledPatch,
    'system'
  );

  return {
    success: true,
    compiled_deltas: [delta],
    target_lut: 'AUTOMATION_RULES',
  };
}

async function compileDictionarySeed(
  structure: DictionarySeedStructure,
  proposal: { entity: Entity; state: DesignProposalData }
): Promise<CompilationResult> {
  // Would create token/pattern/motif entities
  const compiledPatch: JsonPatch[] = [
    { op: 'replace', path: '/compiled_at', value: now() },
  ];

  const { delta } = await createDelta(
    proposal.entity,
    proposal.state,
    compiledPatch,
    'system'
  );

  const targetLut = structure.seed_type === 'token'
    ? 'TOKEN_DICTIONARY'
    : structure.seed_type === 'pattern'
    ? 'PATTERN_DICTIONARY'
    : 'MOTIF_DICTIONARY';

  return {
    success: true,
    compiled_deltas: [delta],
    target_lut: targetLut,
  };
}

// === ORCHESTRATOR ===

export interface AIDesignResult {
  proposals: Array<{ entity: Entity; delta: Delta; state: DesignProposalData }>;
  roleResults: {
    linguist: LinguistOutput;
    architect: ArchitectOutput;
    automator: AutomatorOutput;
    synthesizer: SynthesizerOutput;
  };
}

export async function runAIDesignEngine(
  feeds: DesignInputFeeds
): Promise<AIDesignResult> {
  // Get existing fingerprints for dedup
  const existingFingerprints = new Set(
    feeds.existingDesignProposals
      .filter((p) => p.state.status !== 'REJECTED')
      .map((p) => p.state.fingerprint)
  );

  // Run all roles (isolated, can run in parallel)
  const [linguist, architect, automator, synthesizer] = await Promise.all([
    runLinguistRole(feeds, new Set(existingFingerprints)),
    runArchitectRole(feeds, new Set(existingFingerprints)),
    runAutomatorRole(feeds, new Set(existingFingerprints)),
    runSynthesizerRole(feeds, new Set(existingFingerprints)),
  ]);

  // Combine all proposals
  const allProposals = [
    ...linguist.proposals,
    ...architect.proposals,
    ...automator.proposals,
    ...synthesizer.proposals,
  ];

  return {
    proposals: allProposals,
    roleResults: {
      linguist,
      architect,
      automator,
      synthesizer,
    },
  };
}

// === PROPOSAL ACTIONS ===

export async function reviewDesignProposal(
  entity: Entity,
  state: DesignProposalData,
  decision: 'ACCEPTED' | 'REJECTED',
  notes: string | null = null
): Promise<{ entity: Entity; delta: Delta; state: DesignProposalData }> {
  const patches: JsonPatch[] = [
    { op: 'replace', path: '/status', value: decision },
    { op: 'replace', path: '/reviewed_at', value: now() },
    { op: 'replace', path: '/review_notes', value: notes },
  ];

  return createDelta(entity, state, patches, 'user');
}

// === TRIGGER ===

export function shouldTriggerAIDesign(
  discoveryProposals: Array<{ entity: Entity; state: DiscoveryProposalData }>
): boolean {
  // Trigger when there are accepted discovery proposals to process
  return discoveryProposals.some((p) => p.state.status === 'ACCEPTED');
}
