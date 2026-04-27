// Closed-vocabulary mirror of services/canvas-engine/src/pattern-library/normalize.ts.
// Producer-side checker: keeps the extension's auto-label output in the set of
// detection/kind strings the canvas-engine pattern picker actually recognizes,
// so no region silently falls into the "default" bucket on the consumer.
//
// Two-way contract: when canvas-engine learns a new detection, mirror it here.
// When this file accepts a new detection, mirror it there.

(function () {
  'use strict';

  // Rule prefixes from gatherCandidatesV2's cascade — each maps to "clickable".
  const CLICKABLE_RULE_PREFIXES = ['r2-', 'r3-', 'r4-', 'r5-', 'r7-', 'r8-', 'r9-', 'r11-', 'r12-'];

  // Exact-match clickables (manual + custom + observed).
  const CLICKABLE_LITERALS = new Set([
    'auto-label',
    'alt-click',
    'manual',
    'legacy',
    'custom-element',
    'cursor-dwell',
  ]);

  // Heading detections.
  const HEADING_RX = /^sem-h[1-6]$/;

  // Landmark detections.
  const LANDMARK_LITERALS = new Set([
    'sem-header',
    'sem-footer',
    'sem-nav',
    'sem-main',
    'sem-aside',
    'sem-section',
  ]);

  // Closed kind vocabulary.
  const KIND_VALUES = new Set(['sem', 'click', 'list', 'card', 'custom', 'watch']);

  // Web-audit (lib/anatomy.js) emits a small handful of bare-string detections.
  // Mirrored here so envelopes that come back through the extension (import path)
  // validate without an unknown-detection drop.
  const WEB_AUDIT_LITERALS = new Set([
    'landmark',     // routes to landmark in canvas-engine
    'heading',      // routes to heading
    'button-cluster', // routes to clickable
    'hero',         // routes to clickable
  ]);

  // Full closed detection vocabulary (literals + the 9 rule-prefix patterns + sem-h*).
  // Use isDetectionValid() rather than membership check directly when prefixes apply.
  const DETECTION_LITERALS = new Set([
    ...CLICKABLE_LITERALS,
    ...LANDMARK_LITERALS,
    ...WEB_AUDIT_LITERALS,
    'pattern-repeat',
    'card-heuristic',
    'form',
    'sem-form',
  ]);

  function isDetectionValid(detection) {
    if (!detection) return false;
    const d = String(detection).toLowerCase();
    if (DETECTION_LITERALS.has(d)) return true;
    if (HEADING_RX.test(d)) return true;
    for (const p of CLICKABLE_RULE_PREFIXES) if (d.startsWith(p)) return true;
    return false;
  }

  function groupOfWebAuditLiteral(d) {
    if (d === 'landmark') return 'landmark';
    if (d === 'heading') return 'heading';
    if (d === 'button-cluster' || d === 'hero') return 'clickable';
    return null;
  }

  function isKindValid(kind) {
    if (!kind) return false;
    return KIND_VALUES.has(String(kind).toLowerCase());
  }

  // Mirror of canvas-engine normalize.ts — same group names, same logic order.
  function normalizeDetection(region) {
    const detection = (region && region.detection ? String(region.detection) : '').toLowerCase();
    const kind = (region && region.kind ? String(region.kind) : '').toLowerCase();
    const name = (region && region.name ? String(region.name) : '').toLowerCase();

    if (kind === 'card' || detection === 'card-heuristic') return 'card';
    if (detection === 'pattern-repeat' || kind === 'list') return 'list';
    if (detection === 'form' || detection === 'sem-form' || name === 'form' || name.includes('search bar')) return 'form';
    if (HEADING_RX.test(detection) || detection === 'heading') return 'heading';
    if (LANDMARK_LITERALS.has(detection) || detection === 'landmark') return 'landmark';
    if (CLICKABLE_LITERALS.has(detection)) return 'clickable';
    if (detection === 'button-cluster' || detection === 'hero') return 'clickable';
    for (const p of CLICKABLE_RULE_PREFIXES) if (detection.startsWith(p)) return 'clickable';
    if (kind === 'click' || kind === 'watch') return 'clickable';
    return 'default';
  }

  // Returns { ok, group, fixed } — fixed is a region clone with kind back-filled
  // from detection when the producer forgot to set it. Caller decides whether to
  // accept fixed and warn, or drop the region entirely.
  function validateRegion(region) {
    if (!region || typeof region !== 'object') {
      return { ok: false, group: 'default', reason: 'not-an-object' };
    }
    const detectionOk = isDetectionValid(region.detection);
    if (!detectionOk) {
      return { ok: false, group: 'default', reason: 'unknown-detection: ' + region.detection };
    }
    const group = normalizeDetection(region);
    // Back-fill kind when missing or invalid — keep producer + consumer aligned.
    let fixed = region;
    if (!isKindValid(region.kind)) {
      const inferred = inferKindFromGroup(group, region.detection);
      fixed = Object.assign({}, region, { kind: inferred });
    }
    return { ok: true, group, fixed };
  }

  function inferKindFromGroup(group, detection) {
    if (group === 'card') return 'card';
    if (group === 'list') return 'list';
    if (group === 'heading' || group === 'landmark') return 'sem';
    if (group === 'form') return 'sem';
    if (group === 'clickable') {
      if (detection === 'cursor-dwell') return 'watch';
      if (detection === 'custom-element') return 'custom';
      return 'click';
    }
    return 'custom';
  }

  // Migrate older free-form detection strings to canonical equivalents.
  // Returns the migrated string, or null if the value should be dropped.
  function migrateDetection(rawDetection) {
    if (!rawDetection) return null;
    const d = String(rawDetection).toLowerCase().trim();
    if (isDetectionValid(d)) return d;
    // "cursor dwell · 800ms" → "cursor-dwell"
    if (d.startsWith('cursor dwell')) return 'cursor-dwell';
    // legacy pre-vocab leak — drop, do not pass through.
    return null;
  }

  const VOCAB = {
    DETECTION_LITERALS,
    KIND_VALUES,
    CLICKABLE_RULE_PREFIXES,
    CLICKABLE_LITERALS,
    LANDMARK_LITERALS,
    HEADING_RX,
    isDetectionValid,
    isKindValid,
    normalizeDetection,
    validateRegion,
    inferKindFromGroup,
    migrateDetection,
  };

  // Expose on window for content script consumers; on globalThis for tests.
  if (typeof window !== 'undefined') window.AnatomyDetectionVocab = VOCAB;
  if (typeof globalThis !== 'undefined') globalThis.AnatomyDetectionVocab = VOCAB;
  if (typeof module !== 'undefined' && module.exports) module.exports = VOCAB;
})();
