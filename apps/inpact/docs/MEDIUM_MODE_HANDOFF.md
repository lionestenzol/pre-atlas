# Medium Mode — handoff

**Status:** designed, not built. Parked 2026-07-16 at context ceiling.
**Ask (Bruke, verbatim):** *"i think i need a transition layer bc the big mode is too big
and the minimal mode is too little i need like a medium like transition"*

## The decision that matters: Medium is a filter, not a renderer

**Do NOT write `renderDailyMedium()`.** There are already two renderers
(`renderDailyFull`, `renderDailyMinimal`); a third means three copies of the same page
drifting apart. Medium is **Full with the secondary fields hidden** — one renderer, one
density parameter.

Concretely: `renderDailyFull(plan)` gets a density check, and the secondary blocks render
conditionally. Chapters already collapse (`_chapterOpen`/`_chapterClose`), so Medium is
mostly *"which fields exist"* plus *"which chapters default open"*.

This is the third attempt at this feature. The first two failed by **building a new surface
instead of reducing the existing one**. Don't make it three.

## State

`state.UI.dailyView` becomes `'minimal' | 'medium' | 'full'` (currently `'minimal' | 'full'`).

- Default in `getDefaultState()` — `apps/inpact/js/state.js:160`
- Migration guard — `apps/inpact/js/state.js:257`. Guard is `if (!this.state.UI)`, so it does
  NOT overwrite an existing value. Anyone already holding `'minimal'` keeps it until they click.
- Dispatcher — `apps/inpact/js/screens.js:531`
- Toggle — `_dailyViewToggle(active)` at `apps/inpact/js/screens.js:349`. Currently two pills;
  becomes three. Reuses `.td-btn-pill` + `.active` (`apps/inpact/css/tokens.css:503`).
- Writer — `setDailyView(view)` at `apps/inpact/js/functions.js:2843`. **Widen its validation**:
  it currently hard-rejects anything not `'minimal'`/`'full'` and will silently no-op on `'medium'`.

## What Medium shows (Bruke confirmed, 2026-07-16)

| Section | Medium? | Notes |
|---|---|---|
| Win target | YES, editable | |
| Top 3 priorities | YES, editable | **text only** — no `why` field, no A-Z / PIGPEN link dropdowns (that's 9 controls off the Top 3 block alone) |
| Time blocks | YES, editable | keep completion checkboxes, routine dropdowns, add/remove |
| Goals (baseline + stretch) | YES | with completion toggles |
| Lever + reset move | YES | |
| 3 Ways to Win (x1-3/y1-3) | NO | 6 fields |
| Priority `why` + link selects | NO | `buildLinkSelect('az'/'area', i)` |
| Daily Operating Protocol | NO | |
| Day Mode (A/B/C) | NO | |
| Contingencies | NO | already its own `<details>` |
| Atlas backbone | NO | see suppression below |

Everything excluded is still reachable by switching to Full. Nothing is deleted.

## Implementation sketch

In `renderDailyFull(todayPlan)` (`apps/inpact/js/screens.js:532`):

```js
const dense = state.UI?.dailyView !== 'medium';   // Full renders everything
```

Then gate the secondary markup on `dense`:
- priority `why` input + `buildLinkSelect` calls — `screens.js:566-570`
- "3 Ways to Win" block — `screens.js:574-583`
- Protocol / Day Mode chapters — the `_chapterOpen('protocol'…)` / `_chapterOpen('daymode'…)` blocks
- Contingencies `<details>` — `screens.js:753`

Backbone suppression: `suppressed()` at `apps/inpact/js/backbone.js:93` currently checks
`dailyView === 'minimal'`. Widen to `!== 'full'` so Medium also stays clear of it.

## Definition of Done (tool-provable)

- [ ] `setDailyView('medium')` sets state, persists, and re-renders (note: `stateManager.update`
      saves on a **1000ms debounce** — `state.js:345`. Do not assert persistence synchronously.)
- [ ] Toggle shows 3 pills; the active one carries `.active` + `aria-pressed="true"`
- [ ] In Medium, inside `.max-w-6xl`: `select` count is 0, no `x1`/`y1` inputs, no `p1why` input,
      no `#atlas-backbone`
- [ ] In Medium, win target / p1-p3 / lever / resetMove / time blocks / goals are all present AND
      still write through (`saveTodayField`, `toggleTimeBlockCompletion`, `toggleGoalCompletion`)
- [ ] Full is byte-for-byte unchanged in behaviour — every hidden field returns when you switch back
- [ ] Measured: Medium page height sits between Minimal and Full
- [ ] Verify at 375x812 in the Browser pane, not by reasoning

## Gotchas paid for this session (do not rediscover)

1. **`block.time` has two formats.** Seeded blocks store `'6:00 AM'` (`state.js:68`); blocks edited
   via `input[type=time]` store `'13:00'` (`screens.js:657`). Always normalize through
   `convertTo24Hour()` (`functions.js:297`). A naive `split(':')` sorts the afternoon before the
   morning.
2. **The `toggle` event is async and does not bubble.** Listeners are registered with
   `capture: true`. If you click and assert synchronously, you get a false negative — and if you
   click then `navigate()` in the same tick, the element dies before the event fires and the state
   is genuinely lost. Wait a tick.
3. **The backbone re-mounts itself.** A MutationObserver (`backbone.js:79`) re-inserts it at
   `afterbegin` on every screen swap, so a renderer cannot out-render it. Suppress at the source.
4. **inPACT syncs to delta-kernel** (`AtlasAPI.putCycleBoardState`, `state.js:288`) and :3001 is
   live. Test data written into `state` **will be pushed to the server**. Don't seed junk into
   `state.Routine`/`DayPlans` without cleaning up.
5. **Inline handler attributes need `_jsAttrArg()`** (`screens.js:304`) for any user-controlled
   string. `UI.sanitize` escapes `& < >` only — a quote breaks out of the argument. Routine names
   are free user text.
6. **Don't default the new mode on.** Defaulting Daily to `'minimal'` silently replaced the page
   Bruke uses and read to him as "not even functional". Ship Medium **off by default**; let him
   opt in via the toggle.

## Related

- Festival `inpact-minimal-mode-IM0001` (`festivals/planning/`) — all 6 tasks complete.
  4 quality gates still pending; `apps/inpact` has no test harness, so the TESTING gate has
  nothing to run and needs either a waiver or a harness.
- Commits: `88e1afd` (Minimal Mode), `e4be5c1` (backbone collapse + Full default),
  `ce1883d` (collapsible chapters).
- Open question Bruke hasn't answered: whether to keep Minimal Mode at all. It's behind the
  toggle, defaulted off. If it's reverted, keep the `_jsAttrArg` security fix.
