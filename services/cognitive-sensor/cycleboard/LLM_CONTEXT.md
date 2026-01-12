# CycleBoard - LLM Context Document

> This document provides complete context for an LLM to understand and work with the CycleBoard codebase.

## Project Overview

**CycleBoard** is a browser-based bullet journal/productivity app built with vanilla JavaScript, Tailwind CSS, and localStorage persistence. No build tools or frameworks required.

**Tech Stack:** HTML5, Vanilla JS (ES6+), Tailwind CSS (CDN), Font Awesome icons, localStorage

**Key Concept:** Users plan days using A/B/C day types (energy levels), track 26 lettered monthly tasks (A-Z), manage routines, and journal their progress.

---

## File Structure

```
cycleboard/
├── index.html          # Single HTML entry point with Tailwind CDN
├── css/styles.css      # Custom animations and overrides
└── js/
    ├── state.js        # State management, constants, persistence
    ├── validator.js    # Data validation
    ├── ui.js           # Toasts, modals, loading states
    ├── helpers.js      # Utilities (dates, stats, logging)
    ├── screens.js      # HTML generators for each view
    ├── functions.js    # All action handlers/business logic
    ├── cognitive.js    # Optional cognitive mode system
    └── app.js          # Initialization (loads last)
```

**Load order matters:** state → validator → ui → helpers → screens → functions → cognitive → app

---

## Global Objects & Access Patterns

```javascript
// State manager instance
stateManager              // CycleBoardState instance

// Current state (getter/setter on window)
state                     // Always returns stateManager.state
state.AZTask              // Array of tasks
state.Settings.darkMode   // Boolean

// Utilities
UI.showToast(title, desc, 'success'|'error'|'warning'|'info')
UI.showModal(htmlContent)
UI.closeModal()
UI.sanitize(userInput)    // XSS prevention - ALWAYS use for user data
UI.showLoading(message)
UI.hideLoading()

// Helpers
Helpers.formatDate('2024-01-15')
Helpers.getDayPlan()      // Get/create today's plan
Helpers.logActivity(type, description, details)

// Screen renderers
ScreenRenderers.Home()    // Returns HTML string
ScreenRenderers.Daily()
ScreenRenderers.AtoZ()
// etc.

// Constants (frozen objects)
TASK_STATUS.NOT_STARTED   // 'Not Started'
TASK_STATUS.IN_PROGRESS   // 'In Progress'
TASK_STATUS.COMPLETED     // 'Completed'
DAY_TYPE.A | .B | .C
```

---

## State Structure

```javascript
{
  screen: 'Home',           // Current view name

  AZTask: [{                // Monthly A-Z tasks
    id: 'abc123',
    letter: 'A',            // A-Z
    task: 'Description',
    notes: 'Optional',
    status: 'Not Started',  // Use TASK_STATUS constants
    createdAt: 'ISO string'
  }],

  DayPlans: {               // Keyed by 'YYYY-MM-DD'
    '2024-01-15': {
      date: '2024-01-15',
      day_type: 'A',        // A=optimal, B=low energy, C=chaos
      baseline_goal: { text: '', completed: false },
      stretch_goal: { text: '', completed: false },
      time_blocks: [{ id, time, title, duration, completed }],
      routines_completed: { 'Morning': { completed: false, steps: {} } }
    }
  },

  Routine: {                // Routine definitions
    'Morning': ['Step 1', 'Step 2', 'Step 3'],
    'Evening': ['Step 1', 'Step 2']
  },

  Journal: [{
    id: 'j1234',
    title: 'Entry title',
    content: 'Content...',
    entryType: 'free'|'weekly'|'gratitude',
    tags: [],
    mood: '😊',
    timestamp: 'ISO'
  }],

  History: {
    completedTasks: [{ taskId, completedAt }],
    timeline: [{ id, type, description, timestamp, details }]
  },

  Settings: {
    darkMode: false,
    autoSave: true
  },

  UI: {                     // Transient UI state
    azFilter: 'all',
    azSearch: ''
  }
}
```

---

## Common Patterns

### Creating/Updating Data

```javascript
// Create new item
const newTask = {
  id: stateManager.generateId(),  // Creates unique ID
  letter: 'A',
  task: 'My task',
  status: TASK_STATUS.NOT_STARTED,
  createdAt: new Date().toISOString()
};
state.AZTask.push(newTask);
stateManager.update({ AZTask: state.AZTask });  // Saves to localStorage

// Log activity
Helpers.logActivity('task_created', 'Created task: A', { taskId: newTask.id });

// Re-render
render();

// Show feedback
UI.showToast('Created', 'Task added', 'success');
```

### Modal Pattern

```javascript
function openMyModal() {
  const content = `
    <div class="p-6">
      <h2 class="text-xl font-bold mb-4 dark:text-white">Title</h2>
      <input id="my-input" class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2" />
      <div class="flex justify-end gap-3 mt-6">
        <button onclick="UI.closeModal()" class="px-4 py-2 border rounded-lg">Cancel</button>
        <button onclick="saveMyThing()" class="px-4 py-2 bg-blue-600 text-white rounded-lg">Save</button>
      </div>
    </div>
  `;
  UI.showModal(content);
}
```

### Adding a New Screen

1. Add renderer in `screens.js`:
```javascript
ScreenRenderers.MyScreen = function() {
  return `<div class="space-y-6 fade-in">
    <h1 class="text-3xl font-bold dark:text-white">My Screen</h1>
    <!-- content -->
  </div>`;
};
```

2. Add to navigation in `functions.js` render() function's nav items array

### Filter/Search (using state)

```javascript
// Getters/setters in functions.js
function getAzFilter() { return state.UI?.azFilter || 'all'; }
function setAzFilter(v) { if (!state.UI) state.UI = {}; state.UI.azFilter = v; }

// In screen renderer
const filter = getAzFilter();
const filtered = state.AZTask.filter(t =>
  filter === 'all' || t.status === filter
);
```

---

## Critical Rules

1. **ALWAYS sanitize user input:** `UI.sanitize(userInput)` before inserting into HTML
2. **Use constants:** `TASK_STATUS.COMPLETED` not `'Completed'`
3. **Call render() after state changes** to update the view
4. **Dark mode classes:** Always include `dark:` variants (e.g., `dark:bg-gray-800 dark:text-white`)
5. **Tailwind dynamic classes don't work:** Use `UI.getColorClass('blue', 'bg')` instead of `` `bg-${color}-500` ``
6. **State updates:** Use `stateManager.update({ key: value })` which auto-saves

---

## Key Functions Reference

```javascript
// Navigation
navigate(screenName)          // Switch screens
render()                      // Re-render current screen

// State
stateManager.update(changes)  // Merge & save
stateManager.undo()           // Ctrl+Z
stateManager.redo()           // Ctrl+Shift+Z
stateManager.generateId()     // Unique ID
stateManager.getTodayDate()   // 'YYYY-MM-DD'

// UI
UI.showToast(title, desc, type)
UI.showModal(html)
UI.closeModal()
UI.sanitize(str)
UI.showLoading(msg)
UI.hideLoading()
UI.getColorClass(color, type) // 'blue', 'bg' → 'bg-blue-500'

// Helpers
Helpers.getDayPlan(date?)     // Get/create day plan
Helpers.formatDate(dateStr)   // Human readable
Helpers.logActivity(type, desc, details)
Helpers.getWeeklyStats()
Helpers.getDailyProgress()
```

---

## Validation

```javascript
// Before saving user data
const errors = DataValidator.validateTask(taskObj);
if (errors.length > 0) {
  UI.showToast('Error', errors[0], 'error');
  return;
}
```

Available validators:
- `validateTask(task)` - A-Z task
- `validateDayPlan(plan)` - Day plan
- `validateJournalEntry(entry)` - Journal
- `validateRoutineStep(step)` - Routine step string
- `validateImportData(data)` - Import file

---

## Accessibility Checklist

- Modals: `role="dialog"`, `aria-modal="true"`, escape to close
- Toasts: `role="alert"`, `aria-live="polite"`
- Icons: `aria-hidden="true"` on decorative icons
- Buttons: `aria-label` when text isn't clear
- Focus: Auto-focus first input in modals

---

## Dark Mode

Toggle with `toggleDarkMode()`. Adds `dark` class to `<html>`.

Always use both variants:
```html
<div class="bg-white dark:bg-gray-800 text-black dark:text-white">
```

---

## Data Persistence

- Storage key: `cycleboard-state`
- Auto-saves on changes (debounced 500ms)
- Backup save every 5 minutes
- Save on page unload
- Export: `exportState()` downloads JSON
- Import: `showImportModal()` with validation

---

## Extending the App

### Add new state property:

1. Add to `getDefaultState()` in state.js
2. Add migration in `validator.js` `migrateImportData()`

### Add new action:

1. Add function in `functions.js`
2. Call from HTML `onclick="myFunction()"`

### Add new screen:

1. Add `ScreenRenderers.MyScreen` in screens.js
2. Add nav item in render() function
3. Optionally add to mobile nav in index.html

---

## Example: Complete Feature Addition

Adding a "Quick Notes" feature:

```javascript
// 1. state.js - Add to getDefaultState()
QuickNotes: []

// 2. validator.js - Add migration
if (!migrated.QuickNotes) {
  migrated.QuickNotes = [];
  migratedFeatures.push('QuickNotes');
}

// 3. screens.js - Add renderer
ScreenRenderers.QuickNotes = function() {
  return `
    <div class="space-y-6 fade-in">
      <h1 class="text-3xl font-bold dark:text-white">Quick Notes</h1>
      <button onclick="addQuickNote()" class="px-4 py-2 bg-blue-600 text-white rounded-lg">
        Add Note
      </button>
      <div class="space-y-2">
        ${state.QuickNotes.map(note => `
          <div class="p-4 bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700">
            <p class="dark:text-white">${UI.sanitize(note.text)}</p>
            <button onclick="deleteQuickNote('${note.id}')" class="text-red-500 text-sm">Delete</button>
          </div>
        `).join('')}
      </div>
    </div>
  `;
};

// 4. functions.js - Add actions
function addQuickNote() {
  const text = prompt('Enter note:');
  if (!text) return;

  state.QuickNotes.push({
    id: stateManager.generateId(),
    text: text.trim(),
    createdAt: new Date().toISOString()
  });
  stateManager.update({ QuickNotes: state.QuickNotes });
  render();
  UI.showToast('Added', 'Note saved', 'success');
}

function deleteQuickNote(id) {
  if (!confirm('Delete?')) return;
  state.QuickNotes = state.QuickNotes.filter(n => n.id !== id);
  stateManager.update({ QuickNotes: state.QuickNotes });
  render();
}

// 5. Add to nav in render() function's items array:
{ id: 'QuickNotes', label: 'Quick Notes', icon: 'fa-sticky-note' }
```

---

## Quick Debugging

```javascript
// Check state
console.log(state);
console.log(JSON.stringify(state, null, 2));

// Check specific data
console.log(state.AZTask);
console.log(state.DayPlans[stateManager.getTodayDate()]);

// Force save
stateManager.saveToStorage();

// Check localStorage
localStorage.getItem('cycleboard-state');

// Clear and reset
localStorage.removeItem('cycleboard-state');
location.reload();
```

---

## AI Agent Integration

CycleBoard includes built-in support for AI agents through two modules:

### AIContext - Reading State

```javascript
// Get full context snapshot
const context = AIContext.getContext();

// Get minimal quick context
const quick = AIContext.getQuickContext();

// Get system prompt for LLM
const prompt = AIContext.getSystemPrompt();
```

**Full Context Structure:**
```javascript
{
  _meta: { generatedAt, version, source },
  temporal: { today, todayFormatted, dayOfWeek, currentTime },
  navigation: { currentScreen, availableScreens },
  todayPlan: { dayType, baselineGoal, stretchGoal, timeBlocks, ... },
  progress: { overall, breakdown, streak, weeklyAverage },
  tasks: { all, summary, byStatus, availableLetters },
  routines: { definitions, routineNames, todayCompletion },
  focusAreas: { areas, summary },
  journal: { totalEntries, recentEntries, entriesByType },
  history: { recentActivity, completedTasksCount, streak },
  weeklyStats: { completed, total, percentage },
  cognitive: { mode, risk, openLoops, isClosureMode },
  settings: { ... }
}
```

### AIActions - Modifying State

All methods return `{ success: boolean, ...data }` or `{ success: false, error/errors }`.

**Task Management:**
```javascript
AIActions.createTask('A', 'Task description', 'optional notes');
AIActions.completeTask('taskId');
AIActions.updateTaskStatus('taskId', TASK_STATUS.IN_PROGRESS);
AIActions.updateTask('taskId', { task: 'new text', notes: 'new notes' });
AIActions.findTaskByLetter('A');
```

**Day Planning:**
```javascript
AIActions.setDayType('A');                    // Just change type
AIActions.setDayType('B', true);              // Apply template
AIActions.setGoals('baseline goal', 'stretch goal');
AIActions.toggleGoal('baseline');             // Toggle completion
```

**Time Blocks:**
```javascript
AIActions.addTimeBlock('9:00 AM', 'Deep Work', 90);
AIActions.toggleTimeBlock('blockId');
AIActions.deleteTimeBlock('blockId');
```

**Routines:**
```javascript
AIActions.completeRoutineStep('Morning', 0);  // Complete step by index
AIActions.completeRoutine('Morning');         // Mark entire routine done
```

**Journal:**
```javascript
AIActions.addJournalEntry('Title', 'Content', 'free');  // types: free, weekly, gratitude
```

**Navigation:**
```javascript
AIActions.navigateTo('Daily');  // Valid: Home, Daily, AtoZ, Journal, Routines, etc.
```

**Suggestions:**
```javascript
const suggestion = AIActions.suggestDayType();
// Returns: { suggestion: 'A', reasoning: '...', metrics: {...} }

const nextActions = AIActions.suggestNextAction();
// Returns: [{ priority, action, details, method }, ...]
```

### Example: AI Agent Integration

```javascript
// 1. Get current context
const ctx = AIActions.getContext();

// 2. Analyze and decide on action
if (ctx.progress.overall < 50 && ctx.todayPlan.dayType === 'A') {
  // Suggest switching to B-day
  AIActions.setDayType('B');
}

// 3. Create a task if needed
if (ctx.tasks.availableLetters.includes('C')) {
  AIActions.createTask('C', 'Review weekly goals', 'Suggested by AI');
}

// 4. Log a win
AIActions.addMomentumWin('AI helped optimize the day!');
```

### Connecting External AI (Optional)

To connect CycleBoard to an external AI API (like Claude):

```javascript
// Example bridge function (requires backend)
async function askAI(userMessage) {
  const response = await fetch('/api/ai-chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      systemPrompt: AIContext.getSystemPrompt(),
      context: AIContext.getContext(),
      userMessage: userMessage
    })
  });

  const result = await response.json();

  // Execute any suggested actions
  if (result.actions) {
    result.actions.forEach(action => {
      AIActions[action.method](...action.args);
    });
  }

  return result;
}
```

---

## Summary for LLM Tasks

When asked to modify CycleBoard:

1. **Read relevant files first** - especially the module you're modifying
2. **Follow existing patterns** - look at similar features for style
3. **Use constants** - TASK_STATUS, DAY_TYPE, etc.
4. **Sanitize user input** - UI.sanitize() always
5. **Support dark mode** - Include dark: variants
6. **Update state properly** - stateManager.update() then render()
7. **Add validation** - DataValidator for user input
8. **Log activities** - Helpers.logActivity() for tracking
9. **Show feedback** - UI.showToast() after actions
10. **Test both themes** - Light and dark mode

### For AI Agents:

1. **Use AIContext.getContext()** to understand current state
2. **Use AIActions methods** to make changes (never modify state directly)
3. **Check return values** for success/error before proceeding
4. **Respect day type** - don't suggest heavy work on B/C days
5. **Log activities** - all AIActions methods log with `source: 'AI'`
6. **Use suggestions** - AIActions.suggestDayType() and suggestNextAction()

---

## Copy AI Context Feature

Users can copy a formatted context snapshot to paste into any LLM chat.

### Usage

1. Click **"Copy AI Context"** button in the sidebar
2. Choose format:
   - **Markdown Snapshot** - Human-readable with emojis and tables
   - **System Prompt** - Optimized for AI system prompts
   - **JSON Data** - Full structured data for processing
3. Paste into LLM conversation

### Programmatic Access

```javascript
// Get markdown snapshot (best for chat)
const markdown = AIContext.getClipboardSnapshot();

// Copy to clipboard with UI feedback
await AIContext.copyToClipboard('markdown');  // or 'json' or 'prompt'

// Show the copy modal
showCopyContextModal();
```

### Markdown Snapshot Contents

The markdown snapshot includes:
- Today's overview (date, day type, progress, streak)
- Daily goals with completion status
- Time blocks with checkboxes
- A-Z tasks grouped by status
- Routine completion status
- Progress breakdown with visual bars
- Weekly statistics
- Cognitive state (if active)
- Recent activity log
- Recent journal entries
- Available task letters
