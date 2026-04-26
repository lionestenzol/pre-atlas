// canvas-engine pattern-library · types
// Each pattern is a JSX-source-emitter. The generator picks the highest-scoring
// pattern per region and writes its render() output to the sandbox session.

import type { Chain, Region } from '../adapter/v1-schema.js';

export interface PatternProps {
  componentName: string;
  region: Region;
  chains: Chain[];
}

export interface Pattern {
  /** Unique slug · used in trace logs · e.g. "landmark/header-with-nav" */
  name: string;

  /** The detection-group this pattern services · matched by normalizeDetection() */
  group: PatternGroup;

  /** 0-100 score · higher = better fit. Picker takes argmax. */
  score: (region: Region) => number;

  /** Returns the JSX source code as a string (one default-exported component). */
  render: (props: PatternProps) => string;
}

export type PatternGroup =
  | 'clickable'
  | 'heading'
  | 'landmark'
  | 'list'
  | 'card'
  | 'form'
  | 'default';

export interface PatternRegistry {
  /** All patterns, indexed by group. Always falls back to 'default' if no match. */
  byGroup: Map<PatternGroup, Pattern[]>;
}
