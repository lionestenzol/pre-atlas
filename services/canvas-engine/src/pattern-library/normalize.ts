// canvas-engine pattern-library · detection → pattern group normalizer
// Maps the open vocabulary of region.detection (r12-cursor-pointer, sem-h3, ...)
// to a small set of pattern groups so the registry stays compact.

import type { Region } from '../adapter/v1-schema.js';
import type { PatternGroup } from './types.js';

/**
 * Distribution from the 7-capture survey (655 regions):
 *   clickable  ~80%  (r12-cursor-pointer, r7-native-interactive, r8/r9/r11/r5)
 *   heading    ~10%  (sem-h1...sem-h6)
 *   list       ~4%   (pattern-repeat, kind=list)
 *   landmark   ~2.5% (sem-header/section/main/footer/nav/aside)
 *   card       ~1.4% (card-heuristic, kind=card)
 *   form       ~0.2% (form)
 *   default    everything else
 */
export function normalizeDetection(region: Region): PatternGroup {
  const detection = (region.detection || '').toLowerCase();
  const kind = (region.kind || '').toLowerCase();
  const name = (region.name || '').toLowerCase();

  if (kind === 'card' || detection === 'card-heuristic') return 'card';

  if (
    detection === 'pattern-repeat' ||
    kind === 'list'
  ) return 'list';

  if (
    detection === 'form' ||
    name === 'form' ||
    name.includes('search bar')
  ) return 'form';

  if (/^sem-h[1-6]$/.test(detection)) return 'heading';

  if (
    detection === 'sem-header' ||
    detection === 'sem-footer' ||
    detection === 'sem-nav' ||
    detection === 'sem-main' ||
    detection === 'sem-aside' ||
    detection === 'sem-section'
  ) return 'landmark';

  if (
    detection.startsWith('r5-') ||
    detection.startsWith('r7-') ||
    detection.startsWith('r8-') ||
    detection.startsWith('r9-') ||
    detection.startsWith('r11-') ||
    detection.startsWith('r12-') ||
    kind === 'click'
  ) return 'clickable';

  return 'default';
}
