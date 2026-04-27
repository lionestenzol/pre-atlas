# SPEC 02 · Shadow DOM Recursion

## Problem statement
When a page uses custom elements with shadow roots (either open or closed-but-reachable), `element.outerHTML` returns only the host element's light-DOM children. The shadow root's internal DOM is not included. Serialization loses all visual content that lived inside shadow roots, and the replay renders blank or broken.

## Input
A live `Document` object.

## Required output
A single function `serializeWithShadow(root)` where `root` is a `Document` or an `Element`. Returns a string of HTML.

The returned string must, when parsed and inserted into a fresh document, produce a DOM tree whose rendered output matches the live tree's rendered output for all elements including those inside shadow roots.

## Behavior

1. Walk the element tree starting from `root`.
2. For every element reached, check `element.shadowRoot`. If non-null AND `element.shadowRoot.mode === "open"`, serialize its contents using the declarative shadow DOM syntax.
3. The declarative shadow DOM syntax is: emit a `<template>` child as the first child of the host element, with attribute `shadowrootmode="open"`, containing the shadow root's innerHTML, recursively.
4. If a shadow root has `delegatesFocus === true`, add `shadowrootdelegatesfocus` attribute to the template.
5. Also serialize the shadow root's adopted stylesheets using SPEC 01's function, and prepend those style tags inside the `<template>` element, before the shadow's children.
6. The algorithm recurses: shadow roots inside shadow roots are handled the same way.
7. Closed shadow roots (`mode === "closed"`) are NOT reachable via `element.shadowRoot`. Skip them. The spec does not require defeating closed mode.

## Behavior detail · attribute preservation

For every element's own attributes:
- Preserve all standard attributes as-is.
- Preserve `is="..."` for customized built-ins.
- Preserve `slot="..."` when present.

For `<slot>` elements:
- Preserve `name` attribute.
- Do NOT expand assigned nodes into the slot. The light-DOM children carry their own `slot` attributes that re-bind on replay.

## Failure modes

| condition | required behavior |
|-----------|--------------------|
| element has shadowRoot but mode is closed | skip, do not attempt access |
| element is `<template>` itself | serialize content via its `.content` DocumentFragment, not as a shadow-host pattern |
| element is `<script>` | serialize as-is, do NOT execute, do NOT sanitize |
| circular reference (should not happen; guard anyway) | abort that subtree, continue siblings |

## Out of scope

- Custom element registration (`customElements.define` calls). Replay must register these separately or they render as unknown elements. Not in Plan D.
- ShadowRoot's `.styleSheets` when populated via imperative CSSStyleSheet construction before adoption. Covered by SPEC 01.
- Serializing event listeners. Not possible from outside the page.

## Measurable test cases

| fixture               | setup                                                 | assertion                                                  |
|-----------------------|-------------------------------------------------------|------------------------------------------------------------|
| no-shadow.html        | plain DOM                                             | output equivalent to `outerHTML`                           |
| single-shadow.html    | one custom element, open shadow, `<p>hi</p>` inside   | output contains `<template shadowrootmode="open"><p>hi</p></template>` |
| nested-shadow.html    | shadow inside a shadow                                | both levels present                                         |
| delegates-focus.html  | open shadow with delegatesFocus                       | template has `shadowrootdelegatesfocus`                    |
| closed-shadow.html    | closed shadow root                                    | output does NOT include that shadow's contents             |
| notion-live.html      | captured from `notion.com/product`                    | output has at least one `<template shadowrootmode>`        |
| linear-live.html      | captured from `linear.app/homepage`                   | output has at least one `<template shadowrootmode>`        |

## Definition of done
All seven fixtures pass. On the diff harness's live-URL run against `notion.com/product` and `linear.app/homepage`, the count of `<template shadowrootmode>` tags in the output matches the count of open shadow roots measured in the live page.
