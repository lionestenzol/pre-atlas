# MODULE 5 — AI DESIGN LAYER (Compiler Brain)

**Status:** COMPLETE
**Version:** 1.0.0

---

## Mission

Use LLMs to DESIGN new structure, then compile that structure into deterministic LUTs, templates, and routing rules.

> AI proposes. Humans approve. System compiles.

---

## Laws

1. **AI may NEVER execute runtime actions** — Design only
2. **AI only produces DesignProposal entities** — No direct changes
3. **All outputs require human review** — Before compilation
4. **Compilation produces deterministic LUT updates only** — No AI at runtime

---

## Entity Types

### DesignProposal
```typescript
DesignProposalData {
  proposal_type: DesignProposalType;
  description: string;
  proposed_structure: DesignStructure;
  source_discovery_ids: UUID[];
  confidence: number;
  fingerprint: SHA256;
  status: 'NEW' | 'ACCEPTED' | 'REJECTED';
  designed_by: AIRole;
  created_at: Timestamp;
  reviewed_at: Timestamp | null;
  review_notes: string | null;
  compiled_at: Timestamp | null;
}

DesignProposalType =
  | 'NEW_TEMPLATE'
  | 'ROUTING_PATCH'
  | 'WORKFLOW_SUGGESTION'
  | 'AUTOMATION_RULE'
  | 'DICTIONARY_SEED';
```

---

## AI Roles

| Role | Responsibility | Input | Output |
|------|---------------|-------|--------|
| **Linguist** | Template design | TEMPLATE_SUGGESTION discoveries | NEW_TEMPLATE proposals |
| **Architect** | Routing optimization | ROUTING_SUGGESTION discoveries | ROUTING_PATCH proposals |
| **Automator** | Workflow rules | Task patterns, leverage moves | WORKFLOW_SUGGESTION, AUTOMATION_RULE |
| **Synthesizer** | Dictionary seeds | PATTERN/MOTIF_PROMOTION discoveries | DICTIONARY_SEED proposals |

---

## Role 1: Linguist — Template Design

Converts discovered text patterns into formal templates.

```typescript
interface NewTemplateStructure {
  type: 'NEW_TEMPLATE';
  template_id: string;
  pattern: string;
  slots: string[];
  mode_restriction: Mode | null;
  example_renderings: string[];
}
```

**Inputs:**
- TEMPLATE_SUGGESTION discoveries (accepted)
- Draft usage patterns

**Process:**
1. Refine slot names (standardize)
2. Generate example renderings
3. Set mode restrictions if applicable

---

## Role 2: Architect — Routing Patches

Fixes mode oscillation, stuck states, and skipped progressions.

```typescript
interface RoutingPatchStructure {
  type: 'ROUTING_PATCH';
  target_mode: Mode;
  condition_changes: RoutingConditionPatch[];
  rationale: string;
}

interface RoutingConditionPatch {
  signal: string;
  current_threshold: string;
  proposed_threshold: string;
  effect: string;
}
```

**Issue Fixes:**
| Issue | Fix Strategy |
|-------|-------------|
| LOOP_DETECTED | Widen gap between modes |
| SKIP_DETECTED | Add intermediate checks |
| STUCK_MODE | Relax exit conditions |
| DRIFT | Add temporal smoothing |

---

## Role 3: Automator — Workflow Rules

Creates automation from observed task patterns.

```typescript
interface WorkflowSuggestionStructure {
  type: 'WORKFLOW_SUGGESTION';
  trigger_conditions: Record<string, string>;
  actions: WorkflowAction[];
  mode_applicability: Mode[];
}

interface WorkflowAction {
  action_type: 'create_draft' | 'flag_priority' | 'schedule_review' | 'suggest_template';
  parameters: Record<string, unknown>;
}
```

**Pattern Detection:**
- Multiple BLOCKED tasks → Batch unblock workflow
- Overdue tasks → Escalation workflow
- Project complete → Completion workflow

```typescript
interface AutomationRuleStructure {
  type: 'AUTOMATION_RULE';
  rule_id: string;
  trigger_entity_type: EntityType;
  trigger_conditions: Record<string, unknown>;
  derived_action_type: string;
  action_template: Record<string, unknown>;
}
```

---

## Role 4: Synthesizer — Dictionary Seeds

Promotes patterns/motifs and discovers new tokens.

```typescript
interface DictionarySeedStructure {
  type: 'DICTIONARY_SEED';
  seed_type: 'token' | 'pattern' | 'motif';
  proposed_entries: DictionarySeedEntry[];
}

interface DictionarySeedEntry {
  id: string;
  value: string | string[];
  slots?: string[];
  source_examples: string[];
}
```

**Sources:**
- PATTERN_PROMOTION discoveries → New patterns
- MOTIF_PROMOTION discoveries → New motifs
- High-frequency words in drafts → New tokens

---

## Compilation Gate

All proposals must be ACCEPTED before compilation.

```typescript
interface CompilationResult {
  success: boolean;
  compiled_deltas: Delta[];
  target_lut: string;
  error?: string;
}

function compileDesignProposal(proposal): CompilationResult {
  if (proposal.state.status !== 'ACCEPTED') {
    return { success: false, error: 'Must be ACCEPTED' };
  }
  // Compile to LUT updates
}
```

**Target LUTs by Type:**
| Proposal Type | Target LUT |
|---------------|------------|
| NEW_TEMPLATE | TEMPLATE_CATALOG |
| ROUTING_PATCH | MODE_TRANSITIONS |
| WORKFLOW_SUGGESTION | PREPARATION_WORKFLOWS |
| AUTOMATION_RULE | AUTOMATION_RULES |
| DICTIONARY_SEED | TOKEN/PATTERN/MOTIF_DICTIONARY |

---

## Orchestrator

```typescript
interface DesignInputFeeds {
  discoveryProposals: Array<{ entity: Entity; state: DiscoveryProposalData }>;
  drafts: Array<{ entity: Entity; state: DraftData }>;
  tasks: Array<{ entity: Entity; state: TaskData }>;
  projects: Array<{ entity: Entity; state: ProjectData }>;
  systemState: { entity: Entity; state: SystemStateData };
  existingTemplates: Template[];
  leverageMoves: LeverageMove[];
  tokens: Array<{ entity: Entity; state: TokenData }>;
  patterns: Array<{ entity: Entity; state: PatternData }>;
  motifs: Array<{ entity: Entity; state: MotifData }>;
  routingTransitions: Array<{ from: Mode; to: Mode; count: number }>;
  existingDesignProposals: Array<{ entity: Entity; state: DesignProposalData }>;
}

interface AIDesignResult {
  proposals: Array<{ entity: Entity; delta: Delta; state: DesignProposalData }>;
  roleResults: {
    linguist: LinguistOutput;
    architect: ArchitectOutput;
    automator: AutomatorOutput;
    synthesizer: SynthesizerOutput;
  };
}
```

All roles run in parallel (isolated).

---

## LLM Abstraction

```typescript
interface LLMRequest {
  role: AIRole;
  prompt: string;
  context: Record<string, unknown>;
  max_tokens?: number;
}

interface LLMResponse {
  role: AIRole;
  content: string;
  structured_output: unknown;
  confidence: number;
}

// v0: Deterministic rule-based logic
// Production: Real LLM API calls
async function callLLM(request: LLMRequest): Promise<LLMResponse>
```

---

## Files

| File | Purpose |
|------|---------|
| `ai-design.ts` | Full implementation (~1200 lines) |

---

## Constants

```typescript
MAX_PROPOSALS_PER_ROLE = 5;
MIN_CONFIDENCE_THRESHOLD = 0.6;
```

---

## Key Functions

| Function | Purpose |
|----------|---------|
| `runLinguistRole()` | Design templates |
| `runArchitectRole()` | Design routing patches |
| `runAutomatorRole()` | Design workflows/rules |
| `runSynthesizerRole()` | Design dictionary seeds |
| `runAIDesignEngine()` | Orchestrate all roles |
| `compileDesignProposal()` | Compile to LUT |
| `reviewDesignProposal()` | Accept/reject |
| `shouldTriggerAIDesign()` | Check for accepted discoveries |

---

## Data Flow

```
Module 4 (Discovery Proposals)
           ↓
    ACCEPTED proposals
           ↓
    runAIDesignEngine()
           ↓
    ┌──────┴──────┐
    ↓      ↓      ↓      ↓
Linguist Architect Automator Synthesizer
    ↓      ↓      ↓      ↓
    └──────┬──────┘
           ↓
    DesignProposals (NEW)
           ↓
    Human Review → ACCEPTED
           ↓
    compileDesignProposal()
           ↓
    LUT Updates (deltas)
```

---

## Security Boundary

```
┌─────────────────────────────────────┐
│           DESIGN ZONE               │
│  (AI allowed, proposals only)       │
│                                     │
│  Discovery → Design → Proposal      │
└─────────────────────────────────────┘
                 ↓
         Human Approval
                 ↓
┌─────────────────────────────────────┐
│          EXECUTION ZONE             │
│  (No AI, deterministic only)        │
│                                     │
│  LUTs → Routing → Actions           │
└─────────────────────────────────────┘
```

---

## Trigger Conditions

```typescript
function shouldTriggerAIDesign(discoveryProposals): boolean {
  return discoveryProposals.some(p => p.state.status === 'ACCEPTED');
}
```

---

## Next: Module 6 — Delta Sync Protocol

Synchronize entities and deltas across devices.

Command: **Continue to Module 6 — Delta Sync.**
