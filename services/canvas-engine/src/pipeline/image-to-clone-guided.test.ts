// Offline verification of the FUSED path's deterministic part: turning an
// envelope (the structure map) into the structure-guided vision prompt. No live
// LLM call — we build an envelope from a fixture and assert the guided prompt
// keeps the screenshot as the source of truth while pinning component structure.

import { describe, it, expect } from 'vitest';

import { __test as envTest } from './image-to-envelope.js';
import { buildGuidedInstruction } from './image-to-clone-guided.js';

const MODEL_OUTPUT = `{
  "regions": [
    {"name":"Top Bar","role":"header","desc":"Site header","x":0,"y":0,"w":100,"h":8},
    {"name":"Hero Title","role":"heading","desc":"Page title","x":20,"y":12,"w":60,"h":10},
    {"name":"Get Started","role":"cta","desc":"Primary CTA"}
  ]
}`;

const envelope = envTest.buildEnvelope(MODEL_OUTPUT, 'unit-test', 'cli');

describe('image-to-clone-guided · buildGuidedInstruction', () => {
  const out = buildGuidedInstruction(envelope, 'make it pop');

  it('keeps the base vision replication directive (screenshot is truth)', () => {
    expect(out).toMatch(/looks exactly like the provided screenshot/i);
    expect(out).toMatch(/match the screenshot.*exactly/i);
  });

  it('adds a numbered component plan from the envelope', () => {
    expect(out).toContain('Component plan');
    expect(out).toContain('1. TopBar');
    expect(out).toContain('2. HeroTitle');
    expect(out).toContain('3. GetStarted');
  });

  it('includes a layout hint when bounds are present', () => {
    // "Top Bar" had bounds x0 y0 w100 h8
    expect(out).toContain('[~0,0 100x8%]');
  });

  it('passes the extra intent through the base prompt', () => {
    expect(out).toContain('make it pop');
  });
});
