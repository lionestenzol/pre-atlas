import { describe, expect, it } from 'vitest';
import { isAnchorSelector, isPlaceholderName, leafTag } from '../src/pattern-library/util.js';

describe('isPlaceholderName', () => {
  it('returns true for anatomy placeholder names', () => {
    for (const name of ['header · 1', 'section · 2', 'main · main', 'section', 'Header', 'main']) {
      expect(isPlaceholderName(name)).toBe(true);
    }
  });

  it('returns false for content-like names', () => {
    for (const name of ['Pricing', 'Contact form', 'Save changes', '42']) {
      expect(isPlaceholderName(name)).toBe(false);
    }
  });
});

describe('leafTag', () => {
  it('extracts the tag from bare/single-segment selectors', () => {
    expect(leafTag('a')).toBe('a');
    expect(leafTag('a.cta')).toBe('a');
    expect(leafTag('header')).toBe('header');
    expect(leafTag('header.site-header')).toBe('header');
    expect(leafTag('form.search')).toBe('form');
    expect(leafTag('button:hover')).toBe('button');
  });

  it('extracts the leaf tag from `>` combinator paths', () => {
    expect(leafTag('nav > a')).toBe('a');
    expect(leafTag('td > a > span')).toBe('span');
    expect(leafTag('td > a:nth-of-type(2)')).toBe('a');
    expect(leafTag('div > div > button.primary')).toBe('button');
  });

  it('extracts the leaf tag from descendant whitespace combinators', () => {
    expect(leafTag('nav a')).toBe('a');
    expect(leafTag('main article h2')).toBe('h2');
  });

  it('handles `+` and `~` combinators', () => {
    expect(leafTag('h1 + p')).toBe('p');
    expect(leafTag('h1 ~ p.note')).toBe('p');
  });

  it('returns null when the leaf is class/id/attr/pseudo only', () => {
    expect(leafTag('.foo > .bar')).toBeNull();
    expect(leafTag('[type=button]')).toBeNull();
    expect(leafTag('div > .icon')).toBeNull();
    expect(leafTag('#main')).toBeNull();
  });

  it('returns null for empty/undefined input', () => {
    expect(leafTag(undefined)).toBeNull();
    expect(leafTag('')).toBeNull();
  });
});

describe('isAnchorSelector', () => {
  it('returns true for anchor leaves only', () => {
    expect(isAnchorSelector('a')).toBe(true);
    expect(isAnchorSelector('a.cta')).toBe(true);
    expect(isAnchorSelector('nav > a')).toBe(true);
    expect(isAnchorSelector('td > a:nth-of-type(2)')).toBe(true);
  });

  it('returns false when leaf is not an anchor (ancestor anchors do not count)', () => {
    expect(isAnchorSelector('a > span')).toBe(false);   // ancestor anchor, leaf=span
    expect(isAnchorSelector('a > div > button')).toBe(false);   // leaf=button
    expect(isAnchorSelector('button')).toBe(false);
    expect(isAnchorSelector('header')).toBe(false);
    expect(isAnchorSelector('aside')).toBe(false);
    expect(isAnchorSelector('article')).toBe(false);
  });

  it('returns false for empty/undefined input', () => {
    expect(isAnchorSelector(undefined)).toBe(false);
    expect(isAnchorSelector('')).toBe(false);
  });
});
