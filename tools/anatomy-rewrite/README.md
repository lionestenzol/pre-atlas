# anatomy-rewrite · Plan D Phase 1 scaffold

Clean-room MIT implementation of three DOM serialization capabilities the Anatomy extension needs to preserve fidelity on real SPAs.

## What this is NOT
- NOT a rewrite of SingleFile.
- NOT a generic serialization library.
- NOT cold-fetch-capable.

## What this IS
Three self-contained extension-side capture patches that run inside the user's authenticated browser. Each patch is specified below by BEHAVIOR ONLY and must be implementable without reference to any existing serialization tool.

## The three patches
| # | patch                          | spec                                     |
|---|--------------------------------|------------------------------------------|
| 1 | adopted stylesheet serializer  | `SPEC/01-adopted-stylesheets.md`         |
| 2 | shadow DOM recursion           | `SPEC/02-shadow-dom-recursion.md`        |
| 3 | canvas pre-capture hook        | `SPEC/03-canvas-precapture.md`           |

## Integration target
Each patch plugs into the extension's existing `doPull(mode)` function in `tools/anatomy-extension/content.js`, specifically the raw-mode branch that today calls `outerHTML` + `collectStylesheets()`. These three patches run BEFORE `outerHTML` so the serialized DOM carries their output.

## Firewall rules for implementation
- SPEC documents describe observable behavior. They do not reference any third-party library's source, file names, or function names.
- Implementers must read ONLY the SPEC they are implementing plus the diff harness (`DIFF-HARNESS.md`). They must NOT consult any other serialization tool's source tree.
- Implementations are MIT-licensed. No derivative work.

## Verification
`DIFF-HARNESS.md` describes the test corpus, the metrics, and the pass criteria. Each patch ships when it clears the harness on its relevant fixtures.
