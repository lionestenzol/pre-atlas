# SPEC 01 · Adopted Stylesheet Serializer

## Problem statement
Modern web apps assign CSSStyleSheet objects to `document.adoptedStyleSheets` and `ShadowRoot.adoptedStyleSheets` instead of (or in addition to) inserting `<style>` or `<link rel="stylesheet">` elements. These constructed stylesheets apply to the rendered page but are invisible to `document.documentElement.outerHTML`. When the HTML is serialized and reopened, the page renders unstyled or with missing style rules.

## Input
A live `Document` object in the current page, with zero or more `CSSStyleSheet` instances in:
- `document.adoptedStyleSheets` (array of CSSStyleSheet)
- `shadowRoot.adoptedStyleSheets` for every shadow root reachable from the document

## Required output
A single function `serializeAdoptedStyles(root)` where `root` is a `Document` or `ShadowRoot`. It returns:

```
{
  styleTags: string   // HTML string, zero or more <style> elements
}
```

The `styleTags` string is a concatenation of `<style>` elements that, when injected into a fresh document's `<head>` (for a Document root) or into the shadow root after reconstruction (for a ShadowRoot), produce the same computed styles as the adopted sheets did on the live page.

## Behavior

1. Iterate every entry in `root.adoptedStyleSheets`. For each entry:
   - Read its `cssRules` list.
   - Emit the full `cssText` of each rule in order.
   - Wrap the concatenation in exactly one `<style>` tag.
   - Add an attribute `data-adopted-origin="root"` for document-level sheets, or `data-adopted-origin="shadow"` for shadow-root sheets, so that the replay side can distinguish them during reconstruction.
2. Preserve rule order.
3. Preserve media queries, supports queries, layer declarations, and container queries inside the rule text.
4. If a stylesheet has `disabled === true`, emit the `<style>` tag but also add `data-adopted-disabled="1"`.
5. Output must be HTML-safe: escape any `</style>` literals inside strings by splitting them across adjacent style tags.

## Failure modes

| condition | required behavior |
|-----------|--------------------|
| adoptedStyleSheets unsupported (older browser) | return `{ styleTags: "" }` silently |
| CSSStyleSheet access throws (security) | skip that sheet, continue with remainder |
| Rule `cssText` empty | skip that rule, do not emit empty comment |
| Sheet has zero rules | skip entirely, do not emit empty `<style>` tag |

## Out of scope

- Do NOT handle `<link>` or `<style>` elements here. Those are already captured by existing stylesheet collection.
- Do NOT deduplicate rules across sheets. Order and duplication reflect what the page actually uses.
- Do NOT resolve `@import` URLs. If encountered, emit the `@import` rule verbatim; the fetcher layer resolves it.

## Measurable test cases

Given fixtures in `tests/fixtures/adopted/`:

| fixture           | setup                                                        | assertion                                                      |
|-------------------|--------------------------------------------------------------|----------------------------------------------------------------|
| empty.html        | no adopted sheets                                            | output `styleTags === ""`                                      |
| single.html       | one sheet with one rule `.red { color: red }`               | output contains `.red { color: red }` inside a `<style>` tag    |
| media.html        | one sheet with `@media (max-width: 500px) { .x { color: blue } }` | output preserves the media query wrapping                 |
| shadow.html       | one shadow root with one adopted sheet                       | output distinguishes it with `data-adopted-origin="shadow"`    |
| disabled.html     | one sheet with `disabled = true`                             | output has `data-adopted-disabled="1"`                          |
| linear-live.html  | captured from `linear.app/homepage`                          | at least one `<style data-adopted-origin>` tag in output       |

## Definition of done
All six fixtures pass. On the diff harness's live-URL run against `linear.app/homepage`, the rendered screenshot of the replay is within SSIM ≥ 0.92 of the live page, measured against the same viewport.
