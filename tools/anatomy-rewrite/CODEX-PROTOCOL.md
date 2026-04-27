# Codex Implementation Protocol · Plan D

## Rule zero
Codex sessions implement SPECs blind. The integrity of Plan D's MIT license depends on implementations being independently derived from observable behavior, not copied or restructured from any existing serialization tool.

## What Codex may see
For any given implementation session, Codex is given ONE input:
- The specific `SPEC/<NN>-<name>.md` file for the patch being implemented.

Optionally:
- `DIFF-HARNESS.md` for test structure
- The existing extension file `tools/anatomy-extension/content.js` to identify the integration point (but NOT to copy serialization behavior from — that file does not contain adopted-stylesheet / shadow DOM / canvas logic today, which is why Plan D exists)

## What Codex must NEVER see
- `tools/anatomy-research/vendor-singlefile/` or any file under that tree
- `tools/anatomy-research/vendor-singlefile/RESEARCH_FINDINGS.md`
- `C:\Users\bruke\.claude\projects\C--Users-bruke-Pre-Atlas\memory\project_anatomy_plan_d_clean_room.md` (the baseline memory)
- Any other serialization tool's source tree (dom-to-image, html2canvas, mhtml-to-html, etc.)
- Findings docs that reference specific third-party source structure

## How a Codex session is launched
```
codex exec --dangerously-bypass-approvals-and-sandbox \
  "Implement the function described in tools/anatomy-rewrite/SPEC/01-adopted-stylesheets.md.
   Write the implementation to tools/anatomy-extension/lib/adopted-stylesheets.js.
   Follow the SPEC verbatim; no other input files beyond the SPEC itself and
   the fixtures it references."
```

Never paste the SPEC contents into a session that is also given source-audit material.

## Review protocol
After Codex submits an implementation:
1. Claude (this session) reviews diff against SPEC behavior only, not against any reference source.
2. The diff harness runs. Pass criteria from the SPEC apply.
3. If anything fails, the next Codex session is given:
   - The SPEC (unchanged)
   - A failure report describing observed vs expected behavior for the failing test
   - No source-side analysis

## Implementation boundary · what goes where
Codex writes into `tools/anatomy-extension/lib/` as new files:
- `lib/adopted-stylesheets.js` (from SPEC 01)
- `lib/shadow-dom.js` (from SPEC 02)
- `lib/canvas-precapture.js` (from SPEC 03)

Claude wires those into `content.js` in a SEPARATE change, exposing only the public function signatures defined by each SPEC.

## Why this firewall exists
The baseline memory explains the legal reasoning. The short version: derivative-work risk attaches to source structure and naming, not to solving the same problem. Clean-room separation proves independent derivation. The SPECs are the proof · they read like a product requirements doc, not like annotated reverse-engineering notes.

## If Codex asks for clarification
Claude provides ONE of:
- A targeted edit to the SPEC that clarifies behavior in observable terms
- A new fixture with an expected output

Claude does NOT provide:
- Pseudocode
- Algorithmic hints sourced from reference tools
- Answers like "the other library does X here"
