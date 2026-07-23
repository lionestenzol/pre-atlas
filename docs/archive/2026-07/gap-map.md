# Gap Map: atlas core (CycleBoard) → inPACT

> Read-only inventory, generated 2026-05-24 from live source. The question it answers:
> "I like the inPACT surface and I like the full capabilities of atlas core — how do I get both?"
> Answer: inPACT is the **surface**, atlas core is the **engine**. Keep one front door (inPACT) and
> pull capabilities into it. CycleBoard becomes the parts donor, not a second app to maintain.

## What inPACT already absorbed

CycleBoard has **16 screens**; inPACT has **5**. Not loss — consolidation by timeframe.

| CycleBoard (atlas core) | became in inPACT |
|---|---|
| Home (Strategic HUD) | Home (lighter, HUD dropped) |
| Daily + Routines | Daily |
| AtoZ + Weekly Focus | Tasks |
| Journal + Reflections | History |
| Settings | Settings |
| Command, Energy, Finance, Skills, Network, OSINT, Statistics, Timeline | not carried over |

inPACT kept the **time-based planning spine** + the **8 Steps and cadenced reflections** (both apps
share `positiveAttitude…takeControl` and weekly/monthly/quarterly/yearly reviews). It dropped the
**domain surfaces, analytics, command palette, and AI layer.**

## The gap, capability by capability

| Capability | What it does | Where it lives today | Cost into inPACT |
|---|---|---|---|
| Governance: mode/risk/open-loops | autonomic state readout | delta-kernel (live) + already in inPACT nav | DONE |
| 8 Steps + cadenced reflections | methodology + W/M/Q/Y review | already in inPACT | DONE |
| Timeline | chronological activity feed | DONE: Activity Timeline section in History (reads state.History.timeline) | DONE |
| Statistics | charts over tasks/days | DONE: Statistics section in History (status/day-type bars, 7-day sparkline) | DONE |
| Command palette | keyboard-driven nav + actions | CycleBoard frontend (command.js) | Low–Med |
| Strategic HUD | life phase / burnout / red-alert on Home | strategic.js + cognitive.js (frontend); inputs partly delta-kernel | Med |
| Energy | energy / recovery tracker | CycleBoard frontend only | Med |
| Finance / Runway | cash-runway tracker | CycleBoard frontend only | Med |
| Skills | skill-building tracker | CycleBoard frontend only | Med |
| Network | relationship / contact tracker | CycleBoard frontend only | Med |
| OSINT | intel tracker | CycleBoard frontend only | Med (High if wired to live intel) |
| AI read + act | LLM sees state + takes actions | DONE: inPACT now has ai-context.js (export) + ai-actions.js (API + suggestNextAction) + "Ask Atlas" panel; backend signals (cortex :3009 / optogon :3010) already live | DONE (v1) |

## Three things the map reveals

1. **The 5 domain trackers are the same job five times:** port the screen into inPACT's look + carry
   one state slice. Frontend-only, and since CycleBoard isn't running they're basically empty — no data
   migration, fill fresh. Don't port all 5 blind; pull the one you'd use.
2. **"AI read + act" is the assistant idea already filed — half of it is running** (cortex executes,
   optogon routes). Missing piece = the context-builder that lets it see inPACT's state.
3. **The expensive-sounding stuff is the cheapest:** governance + planning are done; Timeline/Statistics
   are just views over data inPACT already holds.

## Suggested order (value vs cost)

1. Strategic HUD on Home — DONE (shell + execution + live governance tiles)
2. AI read + act — DONE (ai-context.js export + ai-actions.js API + "Ask Atlas" panel; backend signals already live)  ← next: live LLM round-trip via a backend proxy (no key in browser)
3. Timeline + Statistics — DONE (both folded into the History screen)
4. Domain trackers — one at a time, when you'd use it
5. Command palette — power-user nicety
