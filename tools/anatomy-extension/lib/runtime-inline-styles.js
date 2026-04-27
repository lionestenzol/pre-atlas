// Runtime inline stylesheet rehydrator — sibling patch to SPEC 01.
//
// Libraries like styled-components (v6) and emotion create `<style>` elements
// with empty textContent and insert rules at runtime via
// `CSSStyleSheet.insertRule()`. Those rules live in the CSSOM but never appear
// in `outerHTML`, so a vanilla `document.documentElement.outerHTML` capture
// loses them. This module walks every inline `<style>` whose live `cssRules`
// exceed its `textContent`, and re-emits the missing rules as sibling tags.
//
// Exported via `window.__anatomyInlineStyles.serializeRuntimeInlineStyles()`.

(() => {
  'use strict';

  function readRulesText(sheet) {
    const rules = sheet.cssRules;
    if (!rules || !rules.length) return { text: '', count: 0 };
    const parts = [];
    for (let i = 0; i < rules.length; i++) {
      const r = rules[i];
      const t = r && r.cssText;
      if (t) parts.push(t);
    }
    return { text: parts.join('\n'), count: parts.length };
  }

  function escAttr(v) {
    return String(v).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  }

  function passThroughAttrs(el) {
    if (!el || !el.attributes) return '';
    const parts = [];
    for (let i = 0; i < el.attributes.length; i++) {
      const a = el.attributes[i];
      if (a.name === 'data-runtime-rehydrated') continue;
      parts.push(a.name + '="' + escAttr(a.value) + '"');
    }
    return parts.join(' ');
  }

  function wrapAsTags(css, attrStr) {
    const chunks = css.split(/<\/style>/gi).filter((c) => c.length > 0);
    if (chunks.length === 0) return '';
    const prefix = attrStr ? 'data-runtime-rehydrated="1" ' + attrStr : 'data-runtime-rehydrated="1"';
    return chunks.map((c) => '<style ' + prefix + '>' + c + '</style>').join('\n');
  }

  /**
   * Rehydrate inline `<style>` tags whose CSSOM rules exceed their textContent.
   *
   * @returns {{ styleTags: string, rehydratedCount: number }}
   */
  function serializeRuntimeInlineStyles() {
    if (typeof document === 'undefined') return { styleTags: '', rehydratedCount: 0 };
    const els = document.querySelectorAll('style');
    const out = [];
    let rehydrated = 0;

    for (let i = 0; i < els.length; i++) {
      const el = els[i];
      let sheet;
      try { sheet = el.sheet; } catch (_) { continue; }
      if (!sheet) continue;

      let rulesInfo;
      try { rulesInfo = readRulesText(sheet); } catch (_) { continue; }
      if (!rulesInfo.count) continue;

      const textLen = (el.textContent || '').length;
      // If the text already contains most of the rule css, assume it was
      // authored inline and outerHTML will carry it. 0.8 is a safety margin
      // against whitespace differences between cssText and authored text.
      if (textLen >= rulesInfo.text.length * 0.8) continue;

      const attrStr = passThroughAttrs(el);
      const tags = wrapAsTags(rulesInfo.text, attrStr);
      if (tags) {
        out.push(tags);
        rehydrated++;
      }
    }

    return { styleTags: out.join('\n'), rehydratedCount: rehydrated };
  }

  if (typeof window !== 'undefined') {
    window.__anatomyInlineStyles = { serializeRuntimeInlineStyles };
  }
})();
