# SPEC 03 · Canvas Pre-Capture Hook

## Problem statement
`<canvas>` elements render via JavaScript into pixel buffers. When the HTML is serialized, the canvas tag is preserved but the pixel content is not. Replay shows empty canvases where the original had drawings. For apps like whiteboard tools, diagramming apps, or games, this is total visual loss.

## Input
A live `Document` object.

## Required output
A function `precaptureCanvases(root)` that mutates the DOM in place (on the live page, just before serialization) by converting every `<canvas>` into a state-preserving form. Returns `{ count: number }` indicating how many canvases were processed.

After this function runs, calling `outerHTML` on the root captures sufficient information to reconstruct the canvas's visual state on replay.

## Behavior

1. For every `<canvas>` element in the document and in every reachable open shadow root:
   - Read its current pixel buffer via `canvas.toDataURL("image/png")`.
   - If this succeeds, add a `data-precapture-src` attribute to the canvas element with the data URL as its value.
   - Also add `data-precapture-width` and `data-precapture-height` attributes with the canvas's rendered width and height.
2. If `toDataURL` throws (e.g., tainted canvas due to cross-origin content), attempt the following fallback in order:
   a. Try `canvas.toDataURL("image/jpeg", 0.85)` · sometimes bypasses taint checks depending on browser
   b. If still tainted, set `data-precapture-status="tainted"` and skip the content capture
3. Do NOT replace the `<canvas>` element. Keep it in place. The replay logic (separate concern) reads `data-precapture-src` and paints it as the canvas's backdrop.
4. Preserve canvas drawing context (`2d` vs `webgl` vs `webgl2`) inference via `data-precapture-context` attribute. If inference fails, set it to `"unknown"`.

## Context detection
Determine drawing context by attempting in this order:
1. `canvas.getContext("2d", { willReadFrequently: false })` → if non-null, mark as `"2d"`
2. Else try `canvas.getContext("webgl")` via detection: if the canvas has `__webgl` set or `getContext("experimental-webgl")` returns non-null → mark as `"webgl"`
3. Else try `"webgl2"` similarly
4. Else `"unknown"`

Do NOT change the active context. Getting a context binds the canvas permanently in some browsers. Use the context-type detection sparingly · if `getContext("2d")` returns a new context on a canvas that was using webgl, it corrupts the canvas. Prefer checking `canvas.getContext` returns without requesting a new one. (Implementation detail: the `willReadFrequently` flag in step 1 is a no-op semantically but the call itself MUST be tested against the canvas's existing context.)

Safer alternative: inspect `canvas.getAttribute("data-context-hint")` if the page sets it (some apps do). Otherwise fall back to `"unknown"` and let replay re-render.

## Timing constraint
This function MUST run BEFORE any other serialization step (before `outerHTML`, before stylesheet collection) so that:
- Any animation loop that might repaint after the snapshot is captured in its most recent rendered state at serialization time
- The DOM mutation (data-attributes being added) is visible to subsequent serialization

Runtime budget: under 100 ms on a page with up to 10 canvases under 2000×2000 px each. Log a warning if exceeded; do not abort.

## Failure modes

| condition | required behavior |
|-----------|--------------------|
| no canvases on page | return `{ count: 0 }` |
| canvas is 0x0 size | skip, do not emit data attributes |
| toDataURL throws SecurityError | set `data-precapture-status="tainted"` |
| data URL exceeds 10MB | set `data-precapture-status="oversize"`, do not attach |
| getContext polls corrupt existing context | log warning, set `data-precapture-context="unknown"`, continue |

## Out of scope

- WebGL scene graph capture. Only pixel buffer via `toDataURL`.
- Canvas replay logic (reading `data-precapture-src` and rendering). That's a separate runtime concern.
- Video elements. Different surface.
- Animating canvases · we capture one frame, the moment serialization runs.

## Measurable test cases

| fixture               | setup                                                    | assertion                                                     |
|-----------------------|----------------------------------------------------------|---------------------------------------------------------------|
| no-canvas.html        | plain DOM                                                | returns `{ count: 0 }`, no mutations                          |
| blank-canvas.html     | one 100×100 canvas, nothing drawn                        | `data-precapture-src` attribute is set and non-empty          |
| drawn-canvas.html     | one canvas with `fillRect` red square                    | `data-precapture-src` decoded image has red pixels where expected |
| tainted-canvas.html   | canvas drew cross-origin image                           | `data-precapture-status="tainted"` set                        |
| multi-canvas.html     | three canvases                                           | returns `{ count: 3 }`                                         |
| excalidraw-live.html  | captured from `excalidraw.com`                           | at least one canvas has `data-precapture-src` with non-empty image |

## Definition of done
All six fixtures pass. On the diff harness's live-URL run against `excalidraw.com`, the rendered replay shows visible drawing content in the canvas region, not blank. SSIM ≥ 0.80 for the canvas subregion (canvases are hard; threshold lower than SPEC 01).
