// canvas-engine Phase 2 · adapter test suite · vitest

import { describe, it, expect } from 'vitest';

import minimal from './fixtures/anatomy-v1-minimal.json' with { type: 'json' };
import realistic from './fixtures/anatomy-v1-realistic.json' with { type: 'json' };

import {
  anatomyV1Schema,
  type AnatomyV1,
} from '../src/adapter/v1-schema.js';
import {
  buildClonePreamble,
  parseAndBuildClonePreamble,
  type BuildClonePreambleOptions,
} from '../src/adapter/v1-to-prompt.js';
import {
  resolveEditTarget,
  buildEditPrompt,
  type BuildEditPromptOptions,
} from '../src/adapter/v1-to-edit-prompt.js';

const minimalEnvelope: AnatomyV1 = anatomyV1Schema.parse(minimal);
const realisticEnvelope: AnatomyV1 = anatomyV1Schema.parse(realistic);

function buildClone(
  envelope: AnatomyV1,
  opts?: BuildClonePreambleOptions,
): string {
  return buildClonePreamble(envelope, opts);
}

function buildEdit(
  envelope: AnatomyV1,
  opts: BuildEditPromptOptions,
): string {
  return buildEditPrompt(envelope, opts);
}

describe('buildClonePreamble · minimal envelope', () => {
  it('renders the minimal summary and region details', () => {
    const output = buildClone(minimalEnvelope);

    expect(output).toContain('1 regions and 0 backend chain(s)');
    expect(output.startsWith('## Captured structure (anatomy-v1)')).toBe(true);
    expect(output).not.toContain('### Backend chains');
    expect(output).toContain('header');
    expect(output).toContain('Header');
  });
});

describe('buildClonePreamble · realistic envelope', () => {
  it('renders all region, chain, endpoint, and directive data', () => {
    const output = buildClone(realisticEnvelope, { intent: 'clone faithfully' });

    expect(output).toContain('5 regions and 2 backend chain(s)');

    for (const regionId of [
      'header-nav',
      'search-bar',
      'hero',
      'product-grid',
      'footer',
    ]) {
      expect(output).toContain(regionId);
    }

    for (const chainId of ['chain-search', 'chain-products']) {
      expect(output).toContain(chainId);
    }

    for (const fetchUrl of ['/api/me', '/api/search', '/api/products']) {
      expect(output).toContain(fetchUrl);
    }

    expect(output).toContain('### Backend chains (2)');
    expect(output).toContain('### Generation directives');
    expect(output).toContain('Intent: clone faithfully');
  });
});

describe('parseAndBuildClonePreamble · zod validation', () => {
  it('parses a valid minimal envelope without throwing', () => {
    expect(() => parseAndBuildClonePreamble(minimal)).not.toThrow();
  });

  it('throws on a missing required field', () => {
    const invalid = structuredClone(minimal) as Record<string, unknown>;
    delete invalid.version;

    expect(() => parseAndBuildClonePreamble(invalid)).toThrow();
  });

  it('throws on an invalid layer enum', () => {
    const invalid = structuredClone(minimal) as Record<string, unknown>;
    const regions = invalid.regions as Array<Record<string, unknown>>;
    regions[0]!.layer = 'wrongLayer';

    expect(() => parseAndBuildClonePreamble(invalid)).toThrow();
  });

  it('throws on a missing version literal', () => {
    const invalid = {
      ...structuredClone(minimal),
      version: 'not-anatomy-v1',
    };

    expect(() => parseAndBuildClonePreamble(invalid)).toThrow();
  });
});

describe('resolveEditTarget · realistic envelope', () => {
  it('resolves region, chain, and unresolved ids', () => {
    const regionTarget = resolveEditTarget(realisticEnvelope, 'header-nav');
    expect(regionTarget.kind).toBe('region');
    if (regionTarget.kind === 'region') {
      expect(regionTarget.region.id).toBe('header-nav');
    }

    const chainTarget = resolveEditTarget(realisticEnvelope, 'chain-search');
    expect(chainTarget.kind).toBe('chain');
    if (chainTarget.kind === 'chain') {
      expect(chainTarget.chain.id).toBe('chain-search');
    }

    const unresolvedTarget = resolveEditTarget(realisticEnvelope, 'nope');
    expect(unresolvedTarget.kind).toBe('unresolved');
    if (unresolvedTarget.kind === 'unresolved') {
      expect(unresolvedTarget.id).toBe('nope');
    }
  });
});

describe('buildEditPrompt · region target', () => {
  it('renders the targeted region edit prompt', () => {
    const output = buildEdit(realisticEnvelope, {
      intent: 'make it sticky',
      id: 'header-nav',
    });

    expect(output).toContain('Target region: **Header**');
    expect(output).toContain('User intent: make it sticky');
    expect(output).toContain('src/components/Header.tsx:12');
  });
});

describe('buildEditPrompt · chain target', () => {
  it('renders the targeted chain edit prompt', () => {
    const output = buildEdit(realisticEnvelope, {
      intent: 'add caching',
      id: 'chain-search',
    });

    expect(output).toContain('Target chain: **chain-search**');
    expect(output).toContain('n6');
    expect(output).toContain('n7');
    expect(output).toContain('n8');
    expect(output).toContain('n9');
    expect(output).toContain('User intent: add caching');
  });
});

describe('buildEditPrompt · unresolved', () => {
  it('renders the unresolved prompt state', () => {
    const output = buildEdit(realisticEnvelope, {
      intent: 'anything',
      id: 'nonexistent',
    });

    expect(output).toContain('UNRESOLVED');
    expect(output).toContain('nonexistent');
    expect(output).toContain('User intent: anything');
  });
});

describe('regression · prompt grep-passes for endpoint paths', () => {
  it('includes every endpoint path surfaced by regions fetches and api chain nodes', () => {
    const output = buildClone(realisticEnvelope);
    const endpointPaths = new Set<string>();

    for (const region of realisticEnvelope.regions) {
      for (const fetch of region.fetches ?? []) {
        endpointPaths.add(fetch.url);
      }
    }

    for (const chain of realisticEnvelope.chains) {
      for (const node of chain.nodes) {
        if (node.layer === 'api') {
          endpointPaths.add(node.label);
        }
      }
    }

    for (const endpointPath of endpointPaths) {
      expect(output).toContain(endpointPath);
    }
  });
});
