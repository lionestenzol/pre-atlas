// canvas-engine pipeline composition · buildMainBlocks correctness

import { describe, it, expect } from 'vitest';
import {
  buildMainBlocks,
  type RegionComponentSpec,
} from '../src/pipeline/url-to-clone.js';
import type { Pattern, PatternGroup } from '../src/pattern-library/index.js';
import type { Region } from '../src/adapter/v1-schema.js';

function fakePattern(group: PatternGroup, name: string): Pattern {
  return {
    name,
    group,
    score: () => 1,
    render: () => 'export default function X() { return null; }',
  };
}

function fakeSpec(
  group: PatternGroup,
  patternName: string,
  componentName: string,
  n: number,
): RegionComponentSpec {
  const region: Region = {
    id: `r${n}`,
    n,
    name: componentName,
    layer: 'ui',
  };
  return {
    region,
    componentName,
    filePath: `src/components/${componentName}.jsx`,
    pattern: fakePattern(group, patternName),
    slot: 'main',
  };
}

describe('buildMainBlocks · cluster grouping', () => {
  it('runs of <3 same-group specs render as singles', () => {
    const specs = [
      fakeSpec('clickable', 'clickable/button', 'A', 1),
      fakeSpec('clickable', 'clickable/button', 'B', 2),
    ];
    const blocks = buildMainBlocks(specs);
    expect(blocks).toHaveLength(2);
    expect(blocks.every((b) => b.kind === 'single')).toBe(true);
  });

  it('runs of ≥3 same-group specs collapse into a cluster', () => {
    const specs = [
      fakeSpec('clickable', 'clickable/button', 'A', 1),
      fakeSpec('clickable', 'clickable/button', 'B', 2),
      fakeSpec('clickable', 'clickable/pill', 'C', 3),
    ];
    const blocks = buildMainBlocks(specs);
    expect(blocks).toHaveLength(1);
    expect(blocks[0].kind).toBe('cluster');
    if (blocks[0].kind === 'cluster') {
      expect(blocks[0].specs).toHaveLength(3);
    }
  });

  it('different groups break the cluster run', () => {
    const specs = [
      fakeSpec('clickable', 'clickable/button', 'A', 1),
      fakeSpec('clickable', 'clickable/button', 'B', 2),
      fakeSpec('list', 'list/vertical', 'C', 3),
      fakeSpec('clickable', 'clickable/pill', 'D', 4),
    ];
    const blocks = buildMainBlocks(specs);
    // 2 buttons (singles) + 1 list (single) + 1 pill (single) = 4 singles
    expect(blocks).toHaveLength(4);
    expect(blocks.every((b) => b.kind === 'single')).toBe(true);
  });

  it('non-clusterable groups (e.g. landmark) never form clusters', () => {
    const specs = [
      fakeSpec('landmark', 'landmark/section', 'A', 1),
      fakeSpec('landmark', 'landmark/section', 'B', 2),
      fakeSpec('landmark', 'landmark/section', 'C', 3),
      fakeSpec('landmark', 'landmark/section', 'D', 4),
    ];
    const blocks = buildMainBlocks(specs);
    expect(blocks).toHaveLength(4);
    expect(blocks.every((b) => b.kind === 'single')).toBe(true);
  });
});

describe('buildMainBlocks · section grouping', () => {
  it('heading followed by content wraps in a section card', () => {
    const specs = [
      fakeSpec('heading', 'heading/tagged', 'H1', 1),
      fakeSpec('default', 'default/card', 'C1', 2),
    ];
    const blocks = buildMainBlocks(specs);
    expect(blocks).toHaveLength(1);
    expect(blocks[0].kind).toBe('section');
    if (blocks[0].kind === 'section') {
      expect(blocks[0].heading.componentName).toBe('H1');
      expect(blocks[0].children).toHaveLength(1);
    }
  });

  it('back-to-back headings collapse to singles, not empty sections', () => {
    const specs = [
      fakeSpec('heading', 'heading/tagged', 'H1', 1),
      fakeSpec('heading', 'heading/tagged', 'H2', 2),
      fakeSpec('heading', 'heading/tagged', 'H3', 3),
    ];
    const blocks = buildMainBlocks(specs);
    expect(blocks).toHaveLength(3);
    expect(blocks.every((b) => b.kind === 'single')).toBe(true);
  });

  it('section gets a fresh cluster scope · ≥3 clickables under heading cluster', () => {
    const specs = [
      fakeSpec('heading', 'heading/tagged', 'H1', 1),
      fakeSpec('clickable', 'clickable/button', 'A', 2),
      fakeSpec('clickable', 'clickable/button', 'B', 3),
      fakeSpec('clickable', 'clickable/button', 'C', 4),
    ];
    const blocks = buildMainBlocks(specs);
    expect(blocks).toHaveLength(1);
    expect(blocks[0].kind).toBe('section');
    if (blocks[0].kind === 'section') {
      expect(blocks[0].children).toHaveLength(1);
      expect(blocks[0].children[0].kind).toBe('cluster');
    }
  });

  it('pre-heading content stays at top-level, not inside a section', () => {
    const specs = [
      fakeSpec('default', 'default/card', 'Pre', 1),
      fakeSpec('heading', 'heading/tagged', 'H1', 2),
      fakeSpec('default', 'default/card', 'Post', 3),
    ];
    const blocks = buildMainBlocks(specs);
    expect(blocks).toHaveLength(2);
    expect(blocks[0].kind).toBe('single');
    expect(blocks[1].kind).toBe('section');
  });

  it('empty section heading + back-to-back content heading both honored', () => {
    const specs = [
      fakeSpec('heading', 'heading/tagged', 'Empty', 1),
      fakeSpec('heading', 'heading/tagged', 'WithContent', 2),
      fakeSpec('default', 'default/card', 'C', 3),
    ];
    const blocks = buildMainBlocks(specs);
    expect(blocks).toHaveLength(2);
    expect(blocks[0].kind).toBe('single');
    expect(blocks[1].kind).toBe('section');
    if (blocks[1].kind === 'section') {
      expect(blocks[1].heading.componentName).toBe('WithContent');
      expect(blocks[1].children).toHaveLength(1);
    }
  });
});

describe('buildMainBlocks · empty input', () => {
  it('empty specs yields empty blocks', () => {
    expect(buildMainBlocks([])).toEqual([]);
  });
});
