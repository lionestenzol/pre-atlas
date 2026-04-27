// canvas-engine pattern-library · detection → pattern group normalizer
// Maps the open vocabulary of region.detection (r12-cursor-pointer, sem-h3, ...)
// to a small set of pattern groups so the registry stays compact.
//
// Two-way contract with tools/anatomy-extension/lib/detection-vocab.js — when
// a new detection string is added there, mirror it here (and vice versa).

import type { Region } from '../adapter/v1-schema.js';
import type { PatternGroup } from './types.js';
import { leafTag } from './util.js';

/**
 * Distribution from the 7-capture survey (655 regions):
 *   clickable  ~80%  (r12-cursor-pointer, r7-native-interactive, r8/r9/r11/r5)
 *   heading    ~10%  (sem-h1...sem-h6)
 *   list       ~4%   (pattern-repeat, kind=list)
 *   landmark   ~2.5% (sem-header/section/main/footer/nav/aside)
 *   card       ~1.4% (card-heuristic, kind=card)
 *   form       ~0.2% (form)
 *   default    everything else
 *
 * v0.4 vocab additions (extension manual + observation paths):
 *   auto-label, alt-click, manual, legacy, custom-element, cursor-dwell
 *   → all routed to "clickable" so existing captures rebucket cleanly.
 */
// Selector leaf-tag is independent ground truth · the cascade lossy-flattens
// (r7-native-interactive covers <a>, <button>, <input>, <textarea> all the same)
// but the DOM tag in the selector path is browser-emitted and unambiguous.
// Trust the tag for the small set whose group is fixed.
const TAG_OVERRIDES: Record<string, PatternGroup> = {
  input: 'form',
  textarea: 'form',
  select: 'form',
  ul: 'list',
  ol: 'list',
};

export function normalizeDetection(region: Region): PatternGroup {
  const detection = (region.detection || '').toLowerCase();
  const kind = (region.kind || '').toLowerCase();
  const name = (region.name || '').toLowerCase();

  // Tag-based override · the selector path is independent of the cascade.
  const tag = leafTag(region.selector);
  if (tag && TAG_OVERRIDES[tag]) return TAG_OVERRIDES[tag];

  if (kind === 'card' || detection === 'card-heuristic') return 'card';

  if (
    detection === 'pattern-repeat' ||
    kind === 'list'
  ) return 'list';

  if (
    detection === 'form' ||
    detection === 'sem-form' ||
    name === 'form' ||
    name.includes('search bar')
  ) return 'form';

  if (/^sem-h[1-6]$/.test(detection) || detection === 'heading') return 'heading';

  if (
    detection === 'sem-header' ||
    detection === 'sem-footer' ||
    detection === 'sem-nav' ||
    detection === 'sem-main' ||
    detection === 'sem-aside' ||
    detection === 'sem-section' ||
    detection === 'landmark'
  ) return 'landmark';

  if (
    detection.startsWith('r2-') ||
    detection.startsWith('r3-') ||
    detection.startsWith('r4-') ||
    detection.startsWith('r5-') ||
    detection.startsWith('r7-') ||
    detection.startsWith('r8-') ||
    detection.startsWith('r9-') ||
    detection.startsWith('r11-') ||
    detection.startsWith('r12-') ||
    detection === 'auto-label' ||
    detection === 'alt-click' ||
    detection === 'manual' ||
    detection === 'legacy' ||
    detection === 'custom-element' ||
    detection === 'cursor-dwell' ||
    detection === 'button-cluster' ||
    detection === 'hero' ||
    kind === 'click' ||
    kind === 'watch'
  ) return 'clickable';

  return 'default';
}
