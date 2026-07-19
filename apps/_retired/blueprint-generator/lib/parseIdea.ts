import { ParseResult } from './types';

const VAGUE_WORDS = [
  'platform',
  'solution',
  'system',
  'optimize',
  'improve',
  'ai-powered',
  'ai powered',
];

export function parseIdea(input: string): ParseResult {
  const trimmed = input.trim();
  if (!trimmed) {
    return { ok: false, error: 'Input cannot be empty.' };
  }

  const lower = trimmed.toLowerCase();

  const buildingIdx = lower.indexOf('building a ');
  if (buildingIdx === -1) {
    return {
      ok: false,
      error: 'Must follow: "I am building a <product> that helps <user> do <action>"',
    };
  }

  const helpsIdx = lower.indexOf(' that helps ', buildingIdx);
  if (helpsIdx === -1) {
    return {
      ok: false,
      error: 'Missing "that helps". Format: "I am building a <product> that helps <user> do <action>"',
    };
  }

  const doIdx = lower.indexOf(' do ', helpsIdx);
  if (doIdx === -1) {
    return {
      ok: false,
      error: 'Missing "do". Format: "I am building a <product> that helps <user> do <action>"',
    };
  }

  const product = trimmed.slice(buildingIdx + 'building a '.length, helpsIdx).trim();
  const user = trimmed.slice(helpsIdx + ' that helps '.length, doIdx).trim();
  const action = trimmed.slice(doIdx + ' do '.length).trim();

  const segments: [string, string][] = [
    ['product', product],
    ['user', user],
    ['action', action],
  ];

  for (const [label, segment] of segments) {
    const words = segment.split(/\s+/).filter(Boolean);
    if (words.length < 2) {
      return {
        ok: false,
        error: `"${label}" must be at least 2 words. Got: "${segment}"`,
      };
    }
  }

  for (const segment of [product, user, action]) {
    const segLower = segment.toLowerCase();
    for (const vague of VAGUE_WORDS) {
      if (segLower.includes(vague)) {
        return {
          ok: false,
          error: `Rejected: "${vague}" is too vague. Be specific about what you are building.`,
        };
      }
    }
  }

  return { ok: true, data: { product, user, action } };
}
