/**
 * Delta-State Fabric v0 — Template Catalog
 *
 * 12 templates: 6 generic + 6 mode-tagged
 * This is the linguistic kernel for all drafts and messages.
 *
 * LOCKED - No other templates legal in v0.
 */

import { Mode, Template } from './types';

// === TEMPLATE IDS ===

export const TEMPLATE_IDS = {
  // Generic Structural (any mode)
  ACK: 'TEMPLATE_ACK',
  DEFER: 'TEMPLATE_DEFER',
  REQUEST: 'TEMPLATE_REQUEST',
  UPDATE: 'TEMPLATE_UPDATE',
  CLOSE: 'TEMPLATE_CLOSE',
  FOLLOWUP: 'TEMPLATE_FOLLOWUP',

  // Mode-Tagged
  RECOVER_REST: 'TEMPLATE_RECOVER_REST',
  CLOSE_COMMIT: 'TEMPLATE_CLOSE_COMMIT',
  BUILD_OUTLINE: 'TEMPLATE_BUILD_OUTLINE',
  COMPOUND_EXTEND: 'TEMPLATE_COMPOUND_EXTEND',
  SCALE_DELEGATE: 'TEMPLATE_SCALE_DELEGATE',
  SCALE_SYSTEMIZE: 'TEMPLATE_SCALE_SYSTEMIZE',
} as const;

export type TemplateId = (typeof TEMPLATE_IDS)[keyof typeof TEMPLATE_IDS];

// === TEMPLATE CATALOG ===

export const TEMPLATE_CATALOG: Record<TemplateId, Template> = {
  // === GENERIC STRUCTURAL (6) ===

  [TEMPLATE_IDS.ACK]: {
    template_id: TEMPLATE_IDS.ACK,
    slots: [],
    pattern: 'Acknowledged.',
  },

  [TEMPLATE_IDS.DEFER]: {
    template_id: TEMPLATE_IDS.DEFER,
    slots: ['window'],
    pattern: "I'll follow up {window}.",
  },

  [TEMPLATE_IDS.REQUEST]: {
    template_id: TEMPLATE_IDS.REQUEST,
    slots: ['item'],
    pattern: 'Can you send {item}?',
  },

  [TEMPLATE_IDS.UPDATE]: {
    template_id: TEMPLATE_IDS.UPDATE,
    slots: ['status'],
    pattern: 'Update: {status}.',
  },

  [TEMPLATE_IDS.CLOSE]: {
    template_id: TEMPLATE_IDS.CLOSE,
    slots: [],
    pattern: 'Closing this thread.',
  },

  [TEMPLATE_IDS.FOLLOWUP]: {
    template_id: TEMPLATE_IDS.FOLLOWUP,
    slots: ['topic'],
    pattern: 'Following up on {topic}.',
  },

  // === MODE-TAGGED (6) ===

  [TEMPLATE_IDS.RECOVER_REST]: {
    template_id: TEMPLATE_IDS.RECOVER_REST,
    slots: ['time'],
    pattern: "I'm offline until {time} to recover.",
  },

  [TEMPLATE_IDS.CLOSE_COMMIT]: {
    template_id: TEMPLATE_IDS.CLOSE_COMMIT,
    slots: ['time'],
    pattern: 'I will resolve this by {time}.',
  },

  [TEMPLATE_IDS.BUILD_OUTLINE]: {
    template_id: TEMPLATE_IDS.BUILD_OUTLINE,
    slots: ['asset'],
    pattern: 'Here is the outline for {asset}.',
  },

  [TEMPLATE_IDS.COMPOUND_EXTEND]: {
    template_id: TEMPLATE_IDS.COMPOUND_EXTEND,
    slots: ['asset', 'addition'],
    pattern: 'Extending {asset} with {addition}.',
  },

  [TEMPLATE_IDS.SCALE_DELEGATE]: {
    template_id: TEMPLATE_IDS.SCALE_DELEGATE,
    slots: ['task'],
    pattern: 'Please take ownership of {task}.',
  },

  [TEMPLATE_IDS.SCALE_SYSTEMIZE]: {
    template_id: TEMPLATE_IDS.SCALE_SYSTEMIZE,
    slots: ['process'],
    pattern: 'Systemizing {process}.',
  },
};

// === MODE RESTRICTIONS ===

const MODE_TAGGED_TEMPLATES: Record<TemplateId, Mode | null> = {
  // Generic — null means any mode
  [TEMPLATE_IDS.ACK]: null,
  [TEMPLATE_IDS.DEFER]: null,
  [TEMPLATE_IDS.REQUEST]: null,
  [TEMPLATE_IDS.UPDATE]: null,
  [TEMPLATE_IDS.CLOSE]: null,
  [TEMPLATE_IDS.FOLLOWUP]: null,

  // Mode-tagged — must match
  [TEMPLATE_IDS.RECOVER_REST]: 'RECOVER',
  [TEMPLATE_IDS.CLOSE_COMMIT]: 'CLOSE_LOOPS',
  [TEMPLATE_IDS.BUILD_OUTLINE]: 'BUILD',
  [TEMPLATE_IDS.COMPOUND_EXTEND]: 'COMPOUND',
  [TEMPLATE_IDS.SCALE_DELEGATE]: 'SCALE',
  [TEMPLATE_IDS.SCALE_SYSTEMIZE]: 'SCALE',
};

// === GENERIC TEMPLATE SET ===

export const GENERIC_TEMPLATES: TemplateId[] = [
  TEMPLATE_IDS.ACK,
  TEMPLATE_IDS.DEFER,
  TEMPLATE_IDS.REQUEST,
  TEMPLATE_IDS.UPDATE,
  TEMPLATE_IDS.CLOSE,
  TEMPLATE_IDS.FOLLOWUP,
];

// === VALIDATION ===

/**
 * Check if a template is legal for a given mode.
 */
export function isTemplateLegalForMode(
  templateId: string,
  mode: Mode
): boolean {
  const restriction = MODE_TAGGED_TEMPLATES[templateId as TemplateId];

  if (restriction === undefined) {
    // Unknown template — illegal in v0
    return false;
  }

  if (restriction === null) {
    // Generic template — any mode
    return true;
  }

  // Mode-tagged — must match
  return restriction === mode;
}

/**
 * Get all templates legal for a given mode.
 */
export function getTemplatesForMode(mode: Mode): TemplateId[] {
  return Object.entries(MODE_TAGGED_TEMPLATES)
    .filter(([_, restriction]) => restriction === null || restriction === mode)
    .map(([id]) => id as TemplateId);
}

/**
 * Get the mode-specific template for a mode (if any).
 */
export function getModeSpecificTemplate(mode: Mode): TemplateId | null {
  const entry = Object.entries(MODE_TAGGED_TEMPLATES).find(
    ([_, restriction]) => restriction === mode
  );
  return entry ? (entry[0] as TemplateId) : null;
}

// === TEMPLATE RENDERING ===

/**
 * Render a template with given params.
 */
export function renderTemplate(
  templateId: string,
  params: Record<string, string>
): string {
  const template = TEMPLATE_CATALOG[templateId as TemplateId];

  if (!template) {
    // Unknown template — return raw ID with params
    const paramStr = Object.entries(params)
      .map(([k, v]) => `${k}=${v}`)
      .join(', ');
    return paramStr ? `${templateId} (${paramStr})` : templateId;
  }

  let result = template.pattern;

  for (const slot of template.slots) {
    const value = params[slot] || `{${slot}}`;
    result = result.replace(`{${slot}}`, value);
  }

  return result;
}

/**
 * Validate that all required slots are filled.
 */
export function validateTemplateParams(
  templateId: string,
  params: Record<string, string>
): { valid: boolean; missing: string[] } {
  const template = TEMPLATE_CATALOG[templateId as TemplateId];

  if (!template) {
    return { valid: false, missing: ['UNKNOWN_TEMPLATE'] };
  }

  const missing = template.slots.filter((slot) => !params[slot]);

  return {
    valid: missing.length === 0,
    missing,
  };
}

// === MODE-BASED TEMPLATE SELECTION (for workers) ===

/**
 * Get recommended templates for thread triage based on mode.
 */
export function getThreadTriageTemplates(mode: Mode): TemplateId[] {
  switch (mode) {
    case 'RECOVER':
      return [TEMPLATE_IDS.RECOVER_REST, TEMPLATE_IDS.DEFER];
    case 'CLOSE_LOOPS':
      return [TEMPLATE_IDS.CLOSE_COMMIT, TEMPLATE_IDS.ACK, TEMPLATE_IDS.CLOSE];
    case 'BUILD':
      return [TEMPLATE_IDS.DEFER, TEMPLATE_IDS.UPDATE];
    case 'COMPOUND':
      return [TEMPLATE_IDS.UPDATE, TEMPLATE_IDS.FOLLOWUP];
    case 'SCALE':
      return [TEMPLATE_IDS.SCALE_DELEGATE, TEMPLATE_IDS.DEFER];
  }
}

/**
 * Get recommended templates for draft generation based on mode and draft type.
 */
export function getDraftTemplates(
  mode: Mode,
  draftType: 'MESSAGE' | 'ASSET' | 'PLAN' | 'SYSTEM'
): TemplateId[] {
  if (draftType === 'MESSAGE') {
    return getThreadTriageTemplates(mode);
  }

  if (draftType === 'ASSET') {
    switch (mode) {
      case 'BUILD':
        return [TEMPLATE_IDS.BUILD_OUTLINE];
      case 'COMPOUND':
        return [TEMPLATE_IDS.COMPOUND_EXTEND];
      default:
        return [];
    }
  }

  if (draftType === 'PLAN') {
    // Plans use generic templates
    return [TEMPLATE_IDS.UPDATE, TEMPLATE_IDS.FOLLOWUP];
  }

  if (draftType === 'SYSTEM') {
    if (mode === 'SCALE') {
      return [TEMPLATE_IDS.SCALE_SYSTEMIZE, TEMPLATE_IDS.SCALE_DELEGATE];
    }
    return [];
  }

  return [];
}
