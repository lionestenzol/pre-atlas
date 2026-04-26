// canvas-engine pattern-library · registry + picker
// Inventory grows here · each new file in patterns/ gets imported below.
// The picker scores all patterns matching the region's normalized group and
// returns the highest-scoring one. Falls back to the default group if no group
// match is registered.

import type { Region } from '../adapter/v1-schema.js';
import { normalizeDetection } from './normalize.js';
import type { Pattern, PatternGroup, PatternRegistry } from './types.js';

// Pattern imports · alphabetical by file
import cardAction from './patterns/card-action.js';
import cardContent from './patterns/card-content.js';
import cardStat from './patterns/card-stat.js';
import clickableButton from './patterns/clickable-button.js';
import clickableCta from './patterns/clickable-cta.js';
import clickableIconButton from './patterns/clickable-icon-button.js';
import clickableLink from './patterns/clickable-link.js';
import clickablePill from './patterns/clickable-pill.js';
import defaultCard from './patterns/default-card.js';
import formInline from './patterns/form-inline.js';
import formNewsletter from './patterns/form-newsletter.js';
import formStacked from './patterns/form-stacked.js';
import headingEyebrow from './patterns/heading-eyebrow.js';
import headingHero from './patterns/heading-hero.js';
import headingTagged from './patterns/heading-tagged.js';
import landmarkAside from './patterns/landmark-aside.js';
import landmarkFooter from './patterns/landmark-footer.js';
import landmarkHeader from './patterns/landmark-header.js';
import landmarkNav from './patterns/landmark-nav.js';
import landmarkSection from './patterns/landmark-section.js';
import listGrid from './patterns/list-grid.js';
import listTags from './patterns/list-tags.js';
import listVertical from './patterns/list-vertical.js';

const ALL_PATTERNS: Pattern[] = [
  cardAction,
  cardContent,
  cardStat,
  clickableButton,
  clickableCta,
  clickableIconButton,
  clickableLink,
  clickablePill,
  defaultCard,
  formInline,
  formNewsletter,
  formStacked,
  headingEyebrow,
  headingHero,
  headingTagged,
  landmarkAside,
  landmarkFooter,
  landmarkHeader,
  landmarkNav,
  landmarkSection,
  listGrid,
  listTags,
  listVertical,
];

export function buildPatternRegistry(extra: Pattern[] = []): PatternRegistry {
  const byGroup = new Map<PatternGroup, Pattern[]>();
  for (const p of [...ALL_PATTERNS, ...extra]) {
    const arr = byGroup.get(p.group) ?? [];
    arr.push(p);
    byGroup.set(p.group, arr);
  }
  return { byGroup };
}

export interface PickResult {
  pattern: Pattern;
  group: PatternGroup;
  score: number;
}

export function pickPattern(region: Region, registry: PatternRegistry): PickResult {
  const group = normalizeDetection(region);
  const candidates = registry.byGroup.get(group) ?? registry.byGroup.get('default') ?? [];
  if (candidates.length === 0) {
    throw new Error(
      `pattern-library: no patterns for group "${group}" and no default registered`,
    );
  }
  let best = candidates[0];
  let bestScore = best.score(region);
  for (let i = 1; i < candidates.length; i += 1) {
    const s = candidates[i].score(region);
    if (s > bestScore) {
      best = candidates[i];
      bestScore = s;
    }
  }
  return { pattern: best, group, score: bestScore };
}

export type { Pattern, PatternGroup, PatternProps, PatternRegistry } from './types.js';
export { normalizeDetection } from './normalize.js';
