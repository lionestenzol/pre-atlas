// Shadow DOM serializer — SPEC 02 (Plan D · extension-side patch)
//
// `outerHTML` returns only the host element's light-DOM children; any open
// shadow root is invisible. This module walks the tree manually and emits
// declarative shadow DOM via `<template shadowrootmode="open">` so a replayed
// HTML copy reconstructs the shadow tree on parse.
//
// Closed shadow roots (`mode === "closed"`) are not reachable via
// `element.shadowRoot` and are skipped — the spec does not require defeating
// closed mode.
//
// For each open shadow root we also concat its `adoptedStyleSheets` via
// SPEC 01's serializer and prepend the resulting <style> tags inside the
// <template>, before the shadow's children.
//
// Exported via `window.__anatomyShadowDOM.serializeWithShadow(root)`.

(() => {
  'use strict';

  // HTML void elements — no children, no closing tag.
  const VOID = new Set([
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
    'keygen', 'link', 'meta', 'param', 'source', 'track', 'wbr',
  ]);

  // Elements whose textContent is raw and must not be HTML-escaped.
  const RAW_TEXT = new Set(['script', 'style', 'noscript']);

  function escapeText(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function escapeAttr(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;');
  }

  function serializeAttrs(el) {
    if (!el || !el.attributes || !el.attributes.length) return '';
    let out = '';
    for (let i = 0; i < el.attributes.length; i++) {
      const a = el.attributes[i];
      out += ' ' + a.name + '="' + escapeAttr(a.value) + '"';
    }
    return out;
  }

  function adoptedStylesFor(root) {
    try {
      const mod = (typeof window !== 'undefined') ? window.__anatomyAdoptedStyles : null;
      if (!mod || typeof mod.serializeAdoptedStyles !== 'function') return '';
      const r = mod.serializeAdoptedStyles(root);
      return (r && r.styleTags) || '';
    } catch (_) {
      return '';
    }
  }

  // Pre-scan: do we need the slow walk at all? If no open shadow roots in the
  // subtree, the caller can fall back to outerHTML for a faster path.
  function hasOpenShadowRoot(rootEl) {
    if (!rootEl || typeof rootEl.querySelectorAll !== 'function') return false;
    if (rootEl.shadowRoot && rootEl.shadowRoot.mode === 'open') return true;
    let all;
    try { all = rootEl.querySelectorAll('*'); } catch (_) { return false; }
    for (let i = 0; i < all.length; i++) {
      const el = all[i];
      const sr = el.shadowRoot;
      if (sr && sr.mode === 'open') return true;
    }
    return false;
  }

  /**
   * Serialize a Document or Element and any open shadow roots beneath it
   * to an HTML string with declarative shadow-DOM templates inlined.
   *
   * @param {Document | Element} root
   * @returns {string}
   */
  function serializeWithShadow(root) {
    if (!root) return '';
    // Document → serialize its documentElement.
    if (root.nodeType === 9 /* Node.DOCUMENT_NODE */ && root.documentElement) {
      return serializeElement(root.documentElement, new Set(), 0);
    }
    if (root.nodeType !== 1) return '';

    // Fast path: no open shadow root anywhere → outerHTML is sufficient.
    if (!hasOpenShadowRoot(root)) {
      try { return root.outerHTML || ''; } catch (_) { return ''; }
    }
    return serializeElement(root, new Set(), 0);
  }

  // Hard recursion ceiling. Real pages don't approach this; it just prevents
  // a runaway from blowing the stack.
  const MAX_DEPTH = 1024;

  function serializeChildNodes(parent, seenShadows, depth) {
    if (!parent || !parent.childNodes) return '';
    let out = '';
    for (let i = 0; i < parent.childNodes.length; i++) {
      out += serializeNode(parent.childNodes[i], seenShadows, depth);
    }
    return out;
  }

  function serializeNode(node, seenShadows, depth) {
    if (!node) return '';
    if (depth > MAX_DEPTH) return '';
    const t = node.nodeType;
    if (t === 3 /* TEXT_NODE */) return escapeText(node.nodeValue || '');
    if (t === 8 /* COMMENT_NODE */) return '<!--' + (node.nodeValue || '') + '-->';
    if (t === 4 /* CDATA_SECTION_NODE */) return escapeText(node.nodeValue || '');
    if (t === 1 /* ELEMENT_NODE */) return serializeElement(node, seenShadows, depth);
    return '';
  }

  function serializeElement(el, seenShadows, depth) {
    const tag = (el.localName || (el.tagName ? String(el.tagName).toLowerCase() : '')) || 'span';

    // <template> serializes its DocumentFragment, never as a shadow host.
    if (tag === 'template') {
      const inner = el.content
        ? serializeChildNodes(el.content, seenShadows, depth + 1)
        : '';
      return '<template' + serializeAttrs(el) + '>' + inner + '</template>';
    }

    // Raw-text containers: leave content untouched.
    if (RAW_TEXT.has(tag)) {
      const body = (el.textContent != null) ? el.textContent : '';
      return '<' + tag + serializeAttrs(el) + '>' + body + '</' + tag + '>';
    }

    // Void elements: no children, no close.
    if (VOID.has(tag)) {
      return '<' + tag + serializeAttrs(el) + '>';
    }

    let body = '';

    // Open shadow root → declarative shadow DOM template, first child of host.
    let sr = null;
    try { sr = el.shadowRoot; } catch (_) { sr = null; }
    if (sr && sr.mode === 'open' && !seenShadows.has(sr)) {
      seenShadows.add(sr);
      let attrs = ' shadowrootmode="open"';
      if (sr.delegatesFocus) attrs += ' shadowrootdelegatesfocus';
      const adopted = adoptedStylesFor(sr);
      const inner = serializeChildNodes(sr, seenShadows, depth + 1);
      body += '<template' + attrs + '>'
        + (adopted ? adopted + '\n' : '')
        + inner
        + '</template>';
    }

    body += serializeChildNodes(el, seenShadows, depth + 1);

    return '<' + tag + serializeAttrs(el) + '>' + body + '</' + tag + '>';
  }

  if (typeof window !== 'undefined') {
    window.__anatomyShadowDOM = { serializeWithShadow, hasOpenShadowRoot };
  }
})();
