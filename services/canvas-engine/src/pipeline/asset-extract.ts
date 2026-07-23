// canvas-engine · zero-dependency image asset extraction
//
// Answers "what happens to image UI elements in a screenshot": instead of a
// placeholder box, each image region renders a CSS *slice* of the embedded source
// screenshot, positioned to its bounds (the technique proven in element-map). The
// real pixels show with no image library and no pixel decoding in Node.
//
// Source dimensions (PNG only, read from the header) set the slice's aspect ratio
// so it isn't distorted. Unknown dims (jpeg/webp/http) fall back to the raw bound
// ratio · close enough to avoid a zero-height box.

import type { Bounds, Region } from '../adapter/v1-schema.js';

export interface ImageSize {
  w: number;
  h: number;
}

// PNG magic number: 137 80 78 71 13 10 26 10
const PNG_SIGNATURE = '\x89PNG\r\n\x1a\n';

/**
 * Read a PNG's pixel dimensions without decoding it. The IHDR chunk is always
 * first: width is a big-endian uint32 at byte 16, height at byte 20. Returns null
 * for non-PNG data URLs, http(s) URLs, or anything we can't cheaply measure.
 */
export function readPngSize(image: string): ImageSize | null {
  const match = /^data:image\/png;base64,(.+)$/s.exec(image);
  if (match === null) return null;

  let head: Buffer;
  try {
    // 64 base64 chars decode to 48 bytes · more than the 24 we need for IHDR.
    head = Buffer.from(match[1].slice(0, 64), 'base64');
  } catch {
    return null;
  }
  if (head.length < 24) return null;
  if (head.toString('latin1', 0, 8) !== PNG_SIGNATURE) return null;

  const w = head.readUInt32BE(16);
  const h = head.readUInt32BE(20);
  if (w <= 0 || h <= 0) return null;
  return { w, h };
}

/** True when at least one region is a sliceable image asset (image kind + bounds). */
export function hasImageAssets(regions: ReadonlyArray<Region>): boolean {
  return regions.some((r) => r.kind === 'image' && r.bounds !== undefined);
}

/** The shared source module · every slice positions against this one screenshot. */
export function buildSourceModule(image: string): string {
  return [
    '// the original screenshot · every image slice positions against this',
    `export default ${JSON.stringify(image)};`,
    '',
  ].join('\n');
}

// region aspect = (w% · imgW) / (h% · imgH). With unknown dims we fall back to the
// raw bound ratio (assumes a square source) so the box still has a sane shape.
function aspectRatio(b: Bounds, size: ImageSize | null): string {
  const wImg = (size !== null ? size.w : 100) * b.w;
  const hImg = (size !== null ? size.h : 100) * b.h;
  const safeW = wImg > 0 ? wImg : 1;
  const safeH = hImg > 0 ? hImg : 1;
  return `${safeW.toFixed(3)} / ${safeH.toFixed(3)}`;
}

// CSS percentage background-position · aligns the region's edge to the box edge.
// A region spanning the whole axis (span >= 100) pins to 0 to avoid divide-by-zero.
function backgroundPositionPct(offset: number, span: number): number {
  if (span >= 100) return 0;
  return (offset / (100 - span)) * 100;
}

/**
 * A self-contained image-slice component. Scales the embedded screenshot so the
 * region fills the box, then offsets so only that region shows · real pixels, no
 * image processing. Falls back to a labelled placeholder when bounds are missing.
 */
export function buildSliceComponent(
  componentName: string,
  region: Region,
  size: ImageSize | null,
): string {
  const b = region.bounds;
  const label = JSON.stringify(region.name);

  if (b === undefined) {
    return [
      `export default function ${componentName}() {`,
      '  return (',
      '    <div className="flex min-h-[120px] items-center justify-center rounded-lg bg-slate-200 text-sm text-slate-500">',
      `      {${label}}`,
      '    </div>',
      '  );',
      '}',
      '',
    ].join('\n');
  }

  const posX = backgroundPositionPct(b.x, b.w).toFixed(3);
  const posY = backgroundPositionPct(b.y, b.h).toFixed(3);
  const sizeX = (b.w > 0 ? 10000 / b.w : 100).toFixed(3);
  const sizeY = (b.h > 0 ? 10000 / b.h : 100).toFixed(3);
  const ar = aspectRatio(b, size);

  return [
    "import SRC from '../assets/source.js';",
    '',
    "// Real pixels · a CSS slice of the original screenshot at this region's bounds.",
    `export default function ${componentName}() {`,
    '  return (',
    '    <div',
    '      role="img"',
    `      aria-label={${label}}`,
    '      className="w-full overflow-hidden rounded-lg"',
    '      style={{',
    `        aspectRatio: '${ar}',`,
    '        backgroundImage: `url(${SRC})`,',
    "        backgroundRepeat: 'no-repeat',",
    `        backgroundPosition: '${posX}% ${posY}%',`,
    `        backgroundSize: '${sizeX}% ${sizeY}%',`,
    '      }}',
    '    />',
    '  );',
    '}',
    '',
  ].join('\n');
}
