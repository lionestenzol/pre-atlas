"""Fill all task files for cycleboard-wiring festival."""
import pathlib

base = pathlib.Path('/root/festival-project/festivals/planning/cycleboard-wiring-CW0001')

tasks = {}

# ═══ 002_BRAIN_DATA / 01_cognitive_banner ═══
tasks['002_BRAIN_DATA/01_cognitive_banner/01_offline_banner_ui.md'] = """\
# Task: Add Offline Banner UI

## Objective
Add an offline state to the cognitive directive banner so users see a clear message when brain data is unavailable.

## Requirements
- Banner element already exists in index.html (id: cognitive-directive-banner, hidden by default)
- Must show "Cognitive system offline" with instruction to run refresh.py
- Use same Tailwind styling as existing banner but with gray/muted colors
- Must not break existing banner when data IS available

## Implementation Steps
1. Open cycleboard/index.html
2. Find the cognitive-directive-banner div
3. Add an offline variant inside it with id="cognitive-offline-msg"
4. Style: bg-gray-800, text-gray-400, with terminal icon
5. Text: "Cognitive system offline" and smaller text "Run: python refresh.py to generate brain data"

## Definition of Done
- [ ] Offline message element exists in index.html
- [ ] Banner shows offline message when no data loaded
- [ ] Banner shows normal data when cognitive_state.json loads successfully
- [ ] No console errors in either state
"""

tasks['002_BRAIN_DATA/01_cognitive_banner/02_controller_offline_state.md'] = """\
# Task: Update CognitiveController for Offline State

## Objective
Modify CognitiveController in cognitive.js to show the offline banner instead of hiding the entire banner when data fails to load.

## Requirements
- CognitiveController currently hides banner on 404/parse error (display: none)
- Instead: show banner but switch to offline variant
- Log warning to console (keep existing behavior)
- If data loads successfully, show normal banner (existing behavior)

## Implementation Steps
1. Open cycleboard/js/cognitive.js
2. Find the catch/error handler in the data loading function
3. Instead of setting banner display:none, show the banner and display the offline message element
4. Hide the normal data elements (mode, risk, loops, action)
5. On successful load: hide offline message, show normal data elements

## Definition of Done
- [ ] Banner visible in both online and offline states
- [ ] Offline state shows gray message with instructions
- [ ] Online state shows mode/risk/loops/action as before
- [ ] Console warns "Cognitive system offline" (no errors)
"""

# ═══ 002_BRAIN_DATA / 02_strategic_router ═══
tasks['002_BRAIN_DATA/02_strategic_router/01_staleness_detection.md'] = """\
# Task: Add Staleness Detection to Strategic Router

## Objective
Detect when strategic_priorities.json is older than 24 hours and show a warning badge.

## Requirements
- strategic_priorities.json should include a timestamp field (check if it already has one)
- If no timestamp, use file fetch headers (Last-Modified) or fall back to assuming stale
- Threshold: data older than 24 hours = stale
- Warning: yellow badge in strategic card saying "Data is X hours old"

## Implementation Steps
1. Open cycleboard/js/strategic.js
2. In the data loading function, capture the response headers or check for a timestamp field in the JSON
3. Compare against Date.now() - if delta > 24h, set a staleness flag
4. In renderStrategicCard(), if stale flag is set, prepend a yellow warning badge
5. Badge text: "Stale: last updated X hours ago"

## Definition of Done
- [ ] Staleness detected when data > 24h old
- [ ] Yellow warning badge visible in strategic card
- [ ] No warning when data is fresh
- [ ] Graceful handling when timestamp unavailable (assume stale, show "age unknown")
"""

tasks['002_BRAIN_DATA/02_strategic_router/02_timestamp_display.md'] = """\
# Task: Add Last-Updated Timestamp to Strategic Cards

## Objective
Show when strategic data was last generated, so the user knows how current the recommendations are.

## Requirements
- Display timestamp in strategic directive banner and strategic card on Home screen
- Format: relative time ("2 hours ago", "yesterday", "3 days ago")
- Use lightweight relative time formatting (no library needed, simple function)

## Implementation Steps
1. Create a timeAgo(dateString) helper function in strategic.js
2. In renderStrategicCard(), add a small timestamp line below the directive
3. In the strategic directive banner, add timestamp to the right side
4. Style: text-xs, text-gray-500

## Definition of Done
- [ ] Timestamp visible on strategic card
- [ ] Timestamp visible on strategic directive banner
- [ ] Relative time formatting works correctly
- [ ] Graceful fallback when no timestamp available
"""

# ═══ 002_BRAIN_DATA / 03_staleness_warnings ═══
tasks['002_BRAIN_DATA/03_staleness_warnings/01_unified_staleness.md'] = """\
# Task: Unified Staleness Checker

## Objective
Create a single staleness utility that all brain data consumers can use.

## Requirements
- Function: checkStaleness(data, thresholdHours) returns { stale: bool, ageHours: number, ageText: string }
- Works with any brain data JSON that has a timestamp/generated_at field
- Returns human-readable age text
- Default threshold: 24 hours

## Implementation Steps
1. Add a DataFreshness utility object in a new section of cognitive.js (or a shared helpers area)
2. Function accepts a date string and threshold
3. Returns structured result with stale flag, numeric age, and formatted text
4. Wire into both CognitiveController and StrategicRouter data loading

## Definition of Done
- [ ] Utility function exists and is reusable
- [ ] CognitiveController uses it for cognitive_state.json
- [ ] StrategicRouter uses it for strategic_priorities.json
- [ ] Both show appropriate warnings when stale
"""

# ═══ 003_CONTINGENCIES / 01_wire_buttons ═══
tasks['003_CONTINGENCIES/01_wire_buttons/01_contingency_logic.md'] = """\
# Task: Implement Contingency Day Type Switching

## Objective
Make each contingency button apply a real behavioral change to the current day plan.

## Requirements
- Running Late: switch to B-Day template, toast "Switched to B-Day (lighter schedule)"
- Low Energy: switch to C-Day template, toast "Switched to C-Day (minimal schedule)"
- Free Time: add a 90-min stretch block to current plan after the latest existing block
- Disruption: clear remaining time blocks from current time forward, keep completed ones
- Each action must save to state immediately
- Must work even if no day plan exists yet (create one)

## Implementation Steps
1. Open cycleboard/js/functions.js
2. Find activateContingency(type) function (or create it if stubbed)
3. For "runningLate" and "lowEnergy": call applyDayTypeTemplate() with B or C
4. For "freeTime": find latest time block, add a new 90-min stretch block after it
5. For "disruption": filter DayPlans[today].time_blocks to keep only blocks before current time
6. Save state after each action
7. Show toast notification with action description
8. Re-render the Daily screen

## Definition of Done
- [ ] Running Late switches to B-Day
- [ ] Low Energy switches to C-Day
- [ ] Free Time adds stretch block
- [ ] Disruption clears future blocks
- [ ] Toast shown for each action
- [ ] State persisted to localStorage
- [ ] Daily screen re-renders after action
"""

tasks['003_CONTINGENCIES/01_wire_buttons/02_undo_capability.md'] = """\
# Task: Add Undo to Contingency Actions

## Objective
Let users undo a contingency action within 10 seconds via the toast notification.

## Requirements
- Toast notification includes an "Undo" button/link
- Clicking undo reverts to pre-contingency state
- Undo window: 10 seconds (toast auto-dismisses after)
- Uses existing undo/redo system in CycleBoardState

## Implementation Steps
1. Before applying contingency, call state.saveUndoPoint() (or equivalent)
2. Show toast with undo button
3. On undo click: call state.undo(), re-render Daily screen, dismiss toast
4. After 10s: dismiss toast, clear undo reference

## Definition of Done
- [ ] Undo button appears in contingency toast
- [ ] Clicking undo reverts day plan to pre-contingency state
- [ ] Toast auto-dismisses after 10 seconds
- [ ] Undo works for all 4 contingency types
"""

# ═══ 004_STRATEGIC_PERSIST / 01_persist_weights ═══
tasks['004_STRATEGIC_PERSIST/01_persist_weights/01_save_weights.md'] = """\
# Task: Persist Strategic Focus Area Weights

## Objective
Make StrategicRouter.reweightFocusAreas() save the reordered focus areas back to CycleBoardState.

## Requirements
- Currently reweightFocusAreas() sorts areas by weight but does not call state.save()
- After sorting, update state.FocusArea with the new order
- Add a leverageWeight property to each focus area object
- Trigger state save

## Implementation Steps
1. Open cycleboard/js/strategic.js
2. Find reweightFocusAreas() function
3. After sorting, map the sorted results back to state.FocusArea (preserve existing tasks/data, just reorder)
4. Add leverageWeight property from the strategic data to each area
5. Call state.save()
6. Log the reordering to console for debugging

## Definition of Done
- [ ] Focus areas reordered in state after strategic data loads
- [ ] leverageWeight property stored on each focus area
- [ ] State persisted to localStorage
- [ ] WeeklyFocus screen shows areas in new order on next render
"""

tasks['004_STRATEGIC_PERSIST/01_persist_weights/02_weighted_focus_screen.md'] = """\
# Task: Render WeeklyFocus in Weight Order

## Objective
Update the WeeklyFocus screen to render focus areas sorted by leverageWeight (highest first).

## Requirements
- Read leverageWeight from state.FocusArea objects
- Sort descending by leverageWeight (if present), fall back to original order
- Show weight badge on each focus area card
- Badge: small pill showing the weight value (e.g., "0.85")

## Implementation Steps
1. Open cycleboard/js/screens.js
2. Find the WeeklyFocus screen render function
3. Before rendering cards, sort FocusArea by leverageWeight descending
4. Add a weight badge pill to each card header (if leverageWeight exists)
5. Style: bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded-full

## Definition of Done
- [ ] Focus areas sorted by leverage weight
- [ ] Weight badge visible on each card
- [ ] Falls back to default order when no weights exist
- [ ] Visual ordering matches strategic priority
"""

# ═══ 005_DIRECTIVE_SYNC / 01_directive_display ═══
tasks['005_DIRECTIVE_SYNC/01_directive_display/01_load_directive.md'] = """\
# Task: Load Daily Directive in CognitiveController

## Objective
Fetch daily_directive.txt and make it available for display in the CycleBoard UI.

## Requirements
- daily_directive.txt is plain text generated by export_daily_payload.py
- Load alongside cognitive_state.json in CognitiveController init
- Store as CognitiveController.directiveText
- Handle missing file gracefully (null, no error)

## Implementation Steps
1. Open cycleboard/js/cognitive.js
2. In the init/load function, add a fetch for brain/daily_directive.txt
3. If 200: store response.text() as this.directiveText
4. If 404: set this.directiveText = null
5. No parsing needed - it is plain text

## Definition of Done
- [ ] CognitiveController.directiveText populated on successful load
- [ ] Null when file missing (no error)
- [ ] Available for consumption by screens.js
"""

tasks['005_DIRECTIVE_SYNC/01_directive_display/02_render_directive_card.md'] = """\
# Task: Render Directive Card on Home Screen

## Objective
Show the daily directive text as a collapsible card on the Home screen.

## Requirements
- Only render if CognitiveController.directiveText is not null
- Collapsible: starts collapsed, click to expand
- Header: "Daily Directive" with chevron icon
- Body: pre-formatted text (preserve line breaks from .txt)
- Style: matches existing Home screen cards

## Implementation Steps
1. Open cycleboard/js/screens.js
2. Find the Home screen render function
3. After the existing stats section, add the directive card
4. Use a details/summary HTML element for collapsible behavior
5. Render directiveText inside a pre or whitespace-pre-wrap div
6. Only render the card if directiveText is truthy

## Definition of Done
- [ ] Directive card visible on Home screen when data exists
- [ ] Card is collapsible (starts collapsed)
- [ ] Text preserves formatting from the .txt file
- [ ] Card hidden when no directive data
"""

# ═══ 005_DIRECTIVE_SYNC / 02_control_panel_sync ═══
tasks['005_DIRECTIVE_SYNC/02_control_panel_sync/01_unify_mode_calc.md'] = """\
# Task: Unify Control Panel Mode Calculation

## Objective
Remove the independent mode calculation from control_panel.html and have it read from the same source as CycleBoard.

## Requirements
- control_panel.html currently calculates mode inline from closure_ratio
- CycleBoard uses CognitiveController which reads daily_payload.json
- Both should use daily_payload.json as the single source of truth
- Control panel should display the same mode as CycleBoard banner

## Implementation Steps
1. Open services/cognitive-sensor/control_panel.html
2. Find the inline mode calculation logic
3. Replace it with a fetch of brain/daily_payload.json (or cycleboard/brain/daily_payload.json depending on relative path)
4. Read mode from payload.mode field
5. Display mode using same color coding as CycleBoard (BUILD=green, CLOSURE=red, MAINTENANCE=yellow)
6. If payload unavailable, show "Mode: Unknown" instead of calculating a potentially wrong value

## Definition of Done
- [ ] Control panel reads mode from daily_payload.json
- [ ] No inline mode calculation remains
- [ ] Mode matches what CycleBoard shows
- [ ] Graceful fallback when payload missing
"""

# Write all task files
for path, content in tasks.items():
    filepath = base / path
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content)

print(f'Created {len(tasks)} task files')
