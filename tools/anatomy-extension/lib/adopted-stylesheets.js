// Adopted stylesheet serializer — SPEC 01 (Plan D · extension-side patch)
//
// Walks `document.adoptedStyleSheets` or `shadowRoot.adoptedStyleSheets`,
// concatenates each sheet's `cssRules` into a `<style>` tag tagged with
// `data-adopted-origin`. Lets a replayed HTML copy recover constructed
// stylesheets that are invisible to `outerHTML`.
//
// Exported via `window.__anatomyAdoptedStyles.serializeAdoptedStyles(root)`.

(() => {
  'use strict';

  function isShadowRoot(node) {
    return typeof ShadowRoot !== 'undefined' && node instanceof ShadowRoot;
  }

  function originFor(root) {
    return isShadowRoot(root) ? 'shadow' : 'root';
  }

  function readRulesText(sheet) {
    const rules = sheet.cssRules;
    if (!rules || !rules.length) return '';
    const parts = [];
    for (let i = 0; i < rules.length; i++) {
      const rule = rules[i];
      const txt = rule && rule.cssText;
      if (txt) parts.push(txt);
    }
    return parts.join('\n');
  }

  function buildAttrString(origin, disabled) {
    let s = 'data-adopted-origin="' + origin + '"';
    if (disabled) s += ' data-adopted-disabled="1"';
    return s;
  }

  // Any literal `</style>` inside a CSS string would terminate the surrounding
  // <style> tag. Split on it so the terminator is never present in a single
  // tag's body. The `</style>` characters between chunks are lost; real-world
  // CSS almost never contains them inside string literals.
  function wrapAsTags(css, attrString) {
    const chunks = css.split(/<\/style>/gi).filter((c) => c.length > 0);
    if (chunks.length === 0) return '';
    return chunks
      .map((chunk) => '<style ' + attrString + '>' + chunk + '</style>')
      .join('\n');
  }

  /**
   * Serialize constructed stylesheets on the given root as `<style>` tags.
   *
   * @param {Document | ShadowRoot} root
   * @returns {{ styleTags: string }}
   */
  function serializeAdoptedStyles(root) {
    if (!root) return { styleTags: '' };
    const sheets = root.adoptedStyleSheets;
    if (!sheets || !sheets.length) return { styleTags: '' };

    const origin = originFor(root);
    const out = [];

    for (let i = 0; i < sheets.length; i++) {
      const sheet = sheets[i];
      if (!sheet) continue;
      let css = '';
      try {
        css = readRulesText(sheet);
      } catch (_) {
        continue;
      }
      if (!css) continue;

      const attrs = buildAttrString(origin, !!sheet.disabled);
      const tags = wrapAsTags(css, attrs);
      if (tags) out.push(tags);
    }

    return { styleTags: out.join('\n') };
  }

  if (typeof window !== 'undefined') {
    window.__anatomyAdoptedStyles = { serializeAdoptedStyles };
  }
})();
