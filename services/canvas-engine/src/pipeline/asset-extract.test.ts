// Offline verification of zero-dependency image asset extraction: PNG dimension
// reading, the CSS-slice math, and the generator emitting real slices + a shared
// source module for image regions.

import { describe, it, expect } from 'vitest';

import type { Region } from '../adapter/v1-schema.js';
import {
  buildSliceComponent,
  buildSourceModule,
  hasImageAssets,
  readPngSize,
} from './asset-extract.js';
import { generateFromEnvelope } from './url-to-clone.js';
import { __test as envTest } from './image-to-envelope.js';

// Build a 24-byte PNG header (signature + IHDR with given dims) as a data URL.
// readPngSize only inspects the header, so a full PNG body isn't needed.
function pngHeaderDataUrl(w: number, h: number): string {
  const sig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  const ihdrLen = Buffer.from([0, 0, 0, 13]);
  const ihdr = Buffer.from('IHDR', 'latin1');
  const wb = Buffer.alloc(4);
  wb.writeUInt32BE(w, 0);
  const hb = Buffer.alloc(4);
  hb.writeUInt32BE(h, 0);
  const buf = Buffer.concat([sig, ihdrLen, ihdr, wb, hb]);
  return `data:image/png;base64,${buf.toString('base64')}`;
}

describe('asset-extract · readPngSize', () => {
  it('reads width/height from a PNG header', () => {
    expect(readPngSize(pngHeaderDataUrl(1536, 678))).toEqual({ w: 1536, h: 678 });
  });

  it('returns null for non-PNG data URLs', () => {
    expect(readPngSize('data:image/jpeg;base64,AAAA')).toBeNull();
  });

  it('returns null for http(s) URLs', () => {
    expect(readPngSize('https://example.com/x.png')).toBeNull();
  });
});

describe('asset-extract · hasImageAssets', () => {
  const img: Region = { id: 'a-1', n: 1, name: 'A', layer: 'ui', kind: 'image', bounds: { x: 0, y: 0, w: 10, h: 10 } };
  const noBounds: Region = { id: 'b-2', n: 2, name: 'B', layer: 'ui', kind: 'image' };
  const text: Region = { id: 'c-3', n: 3, name: 'C', layer: 'ui' };

  it('is true only when an image region has bounds', () => {
    expect(hasImageAssets([img, text])).toBe(true);
    expect(hasImageAssets([noBounds, text])).toBe(false);
    expect(hasImageAssets([text])).toBe(false);
  });
});

describe('asset-extract · buildSourceModule', () => {
  it('default-exports the (safely quoted) source URL', () => {
    const out = buildSourceModule('data:image/png;base64,ZZZ');
    expect(out).toContain('export default "data:image/png;base64,ZZZ"');
  });
});

describe('asset-extract · buildSliceComponent', () => {
  const region: Region = {
    id: 'hero-1',
    n: 1,
    name: 'Hero',
    layer: 'ui',
    kind: 'image',
    bounds: { x: 10, y: 20, w: 30, h: 40 },
  };

  it('slices the embedded source with correct CSS percentage math', () => {
    const out = buildSliceComponent('Hero', region, { w: 1000, h: 500 });
    expect(out).toContain("import SRC from '../assets/source.js'");
    expect(out).toContain('role="img"');
    // x/(100-w) = 10/70 = 14.286 ; y/(100-h) = 20/60 = 33.333
    expect(out).toContain("backgroundPosition: '14.286% 33.333%'");
    // 10000/w and 10000/h
    expect(out).toContain("backgroundSize: '333.333% 250.000%'");
  });

  it('falls back to a labelled placeholder when bounds are missing', () => {
    const noBounds: Region = { id: 'logo-1', n: 1, name: 'Logo', layer: 'ui', kind: 'image' };
    const out = buildSliceComponent('Logo', noBounds, null);
    expect(out).toContain('{"Logo"}');
    expect(out).not.toContain('import SRC');
  });
});

describe('asset-extract · generateFromEnvelope integration', () => {
  const MODEL = `{
    "regions": [
      {"name":"Hero Photo","role":"image","x":0,"y":0,"w":50,"h":30},
      {"name":"Title","role":"heading","x":0,"y":35,"w":100,"h":10}
    ]
  }`;
  const envelope = envTest.buildEnvelope(MODEL, 'unit-test', 'cli');

  it('emits a source module and slices the image region when given the screenshot', () => {
    const files = generateFromEnvelope(envelope, {
      imageSrc: 'data:image/png;base64,AAAA',
      imageSize: { w: 100, h: 60 },
    });
    expect(files.some((f) => f.path === 'src/assets/source.js')).toBe(true);
    expect(
      files.some((f) => f.content.includes("import SRC from '../assets/source.js'")),
    ).toBe(true);
  });

  it('does NOT emit a source module on the plain (url) path', () => {
    const files = generateFromEnvelope(envelope);
    expect(files.some((f) => f.path === 'src/assets/source.js')).toBe(false);
    expect(files.some((f) => f.content.includes('import SRC'))).toBe(false);
  });
});
