# CycleBoard API Reference

Complete API documentation for all modules and functions.

---

## Table of Contents

1. [Constants](#constants)
2. [CycleBoardState Class](#cycleboardstate-class)
3. [DataValidator Class](#datavalidator-class)
4. [UI Object](#ui-object)
5. [Helpers Object](#helpers-object)
6. [ScreenRenderers Object](#screenrenderers-object)
7. [CognitiveController Object](#cognitivecontroller-object)
8. [Global Functions](#global-functions)

---

## Constants

### TASK_STATUS

Frozen object containing valid task status values.

```javascript
const TASK_STATUS = Object.freeze({
  NOT_STARTED: 'Not Started',
  IN_PROGRESS: 'In Progress',
  COMPLETED: 'Completed'
});
```

**Usage:**
```javascript
task.status = TASK_STATUS.COMPLETED;
if (task.status === TASK_STATUS.IN_PROGRESS) { ... }
```

### DAY_TYPE

Frozen object containing valid day type values.

```javascript
const DAY_TYPE = Object.freeze({
  A: 'A',  // Optimal day
  B: 'B',  // Low energy day
  C: 'C'   // Chaos/survival day
});
```

### REFLECTION_PERIOD

Frozen object containing reflection period types.

```javascript
const REFLECTION_PERIOD = Object.freeze({
  WEEKLY: 'weekly',
  MONTHLY: 'monthly',
  QUARTERLY: 'quarterly',
  YEARLY: 'yearly'
});
```

---

## CycleBoardState Class

State management class handling persistence, undo/redo, and data operations.

### Constructor

```javascript
const stateManager = new CycleBoardState();
```

Creates a new state manager, loading existing state from localStorage or initializing defaults.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `state` | Object | Current application state |
| `history` | Array | Undo history stack |
| `historyIndex` | Number | Current position in history |
| `maxHistorySize` | Number | Maximum history entries (default: 50) |

### Methods

#### loadFromStorage()

```javascript
stateManager.loadFromStorage();
```

Loads state from localStorage. Called automatically in constructor.

#### saveToStorage()

```javascript
stateManager.saveToStorage();
```

Persists current state to localStorage. Automatically called by `update()` with debouncing.

#### update(changes)

```javascript
stateManager.update({
  Settings: { darkMode: true },
  screen: 'Daily'
});
```

Merges changes into state, pushes to history, and triggers debounced save.

**Parameters:**
- `changes` (Object): Partial state object to merge

#### undo()

```javascript
const success = stateManager.undo();
```

Reverts to previous state in history.

**Returns:** `boolean` - True if undo was performed

#### redo()

```javascript
const success = stateManager.redo();
```

Re-applies previously undone state.

**Returns:** `boolean` - True if redo was performed

#### generateId()

```javascript
const id = stateManager.generateId();
// Returns: "abc123def456"
```

Generates a unique 12-character alphanumeric ID.

**Returns:** `string` - Unique identifier

#### getTodayDate()

```javascript
const today = stateManager.getTodayDate();
// Returns: "2024-01-15"
```

Gets current date in YYYY-MM-DD format.

**Returns:** `string` - ISO date string

#### getDefaultState()

```javascript
const defaults = stateManager.getDefaultState();
```

Returns a fresh default state object with all required properties.

**Returns:** `Object` - Default state structure

#### getState()

```javascript
const stateCopy = stateManager.getState();
```

Returns a shallow copy of current state.

**Returns:** `Object` - State copy

---

## DataValidator Class

Static validation methods for data integrity.

### validateTask(task)

```javascript
const errors = DataValidator.validateTask({
  letter: 'A',
  task: 'Complete project',
  status: 'In Progress'
});
// Returns: [] or ['Error message']
```

Validates an A-Z task object.

**Parameters:**
- `task` (Object): Task to validate
  - `letter` (string): Single uppercase letter A-Z
  - `task` (string): Description (max 500 chars)
  - `notes` (string, optional): Notes (max 2000 chars)
  - `status` (string): Valid TASK_STATUS value

**Returns:** `Array<string>` - Validation errors (empty if valid)

### validateDayPlan(plan)

```javascript
const errors = DataValidator.validateDayPlan({
  date: '2024-01-15',
  day_type: 'A',
  rating: 4
});
```

Validates a day plan object.

**Parameters:**
- `plan` (Object): Day plan to validate
  - `date` (string): YYYY-MM-DD format
  - `day_type` (string): A, B, or C
  - `rating` (number, optional): 0-5

**Returns:** `Array<string>` - Validation errors

### validateJournalEntry(entry)

```javascript
const errors = DataValidator.validateJournalEntry({
  title: 'My Entry',
  content: 'Journal content...'
});
```

Validates a journal entry.

**Parameters:**
- `entry` (Object): Journal entry
  - `title` (string): Title (max 200 chars)
  - `content` (string): Content (max 5000 chars)

**Returns:** `Array<string>` - Validation errors

### validateRoutineStep(step)

```javascript
const errors = DataValidator.validateRoutineStep('Brush teeth');
```

Validates a routine step string.

**Parameters:**
- `step` (string): Step description (max 200 chars, non-empty)

**Returns:** `Array<string>` - Validation errors

### validateImportData(data)

```javascript
const errors = DataValidator.validateImportData(importedJson);
```

Validates imported backup data structure.

**Parameters:**
- `data` (Object): Parsed JSON import

**Returns:** `Array<string>` - Validation errors

### migrateImportData(data, defaults)

```javascript
const { migrated, migratedFeatures } = DataValidator.migrateImportData(
  importedData,
  stateManager.getDefaultState()
);
```

Fills missing properties from older backup versions.

**Parameters:**
- `data` (Object): Import data
- `defaults` (Object): Default state for missing values

**Returns:** `Object`
- `migrated` (Object): Complete state with defaults filled
- `migratedFeatures` (Array<string>): List of added features

---

## UI Object

User interface utilities for notifications, modals, and loading states.

### sanitize(input)

```javascript
const safe = UI.sanitize('<script>alert("xss")</script>');
// Returns: "&lt;script&gt;alert("xss")&lt;/script&gt;"
```

Escapes HTML to prevent XSS attacks.

**Parameters:**
- `input` (any): Value to sanitize

**Returns:** `string` - HTML-escaped string

### showToast(title, description, type)

```javascript
UI.showToast('Success', 'Task completed!', 'success');
UI.showToast('Error', 'Something went wrong', 'error');
UI.showToast('Warning', 'Check your input', 'warning');
UI.showToast('Info', 'Did you know...', 'info');
```

Displays a toast notification that auto-dismisses after 3 seconds.

**Parameters:**
- `title` (string): Toast title
- `description` (string, optional): Additional details
- `type` (string): 'success' | 'error' | 'warning' | 'info'

### showModal(content)

```javascript
UI.showModal(`
  <div class="p-6">
    <h2 class="text-xl font-bold">Modal Title</h2>
    <p>Modal content here...</p>
    <button onclick="UI.closeModal()">Close</button>
  </div>
`);
```

Opens a modal dialog with the provided HTML content.

**Parameters:**
- `content` (string): HTML content for modal body

**Notes:**
- User data must be sanitized with `UI.sanitize()` before inclusion
- Pressing Escape closes the modal
- Clicking backdrop closes the modal
- Focus is automatically managed

### closeModal()

```javascript
UI.closeModal();
```

Closes the currently open modal and restores focus.

### showLoading(message)

```javascript
UI.showLoading('Importing data...');
```

Shows a full-screen loading overlay.

**Parameters:**
- `message` (string, optional): Loading message (default: 'Loading...')

### hideLoading()

```javascript
UI.hideLoading();
```

Removes the loading overlay.

### spinnerHtml(size)

```javascript
const spinner = UI.spinnerHtml('sm');
button.innerHTML = spinner + ' Saving...';
```

Returns HTML for an inline loading spinner.

**Parameters:**
- `size` (string): 'sm' | 'md' | 'lg'

**Returns:** `string` - Spinner HTML

### getColorClass(color, type)

```javascript
const bgClass = UI.getColorClass('blue', 'bg');      // 'bg-blue-500'
const textClass = UI.getColorClass('green', 'text'); // 'text-green-500'
```

Gets Tailwind color classes (prevents purging of dynamic classes).

**Parameters:**
- `color` (string): 'blue' | 'green' | 'purple' | 'orange' | 'yellow' | 'red' | 'amber'
- `type` (string): 'bg' | 'bgLight' | 'bgDark' | 'text' | 'textDark'

**Returns:** `string` - Tailwind class name

### renderProgressRing(percentage, size, stroke)

```javascript
const svg = UI.renderProgressRing(75, 40, 4);
```

Generates an SVG progress ring.

**Parameters:**
- `percentage` (number): 0-100
- `size` (number, optional): Diameter in pixels (default: 40)
- `stroke` (number, optional): Stroke width (default: 4)

**Returns:** `string` - SVG HTML

### updateDateDisplay()

```javascript
UI.updateDateDisplay();
```

Updates the date display element in the header.

---

## Helpers Object

Utility functions for dates, calculations, and logging.

### formatDate(dateStr)

```javascript
const formatted = Helpers.formatDate('2024-01-15');
// Returns: "Monday, January 15, 2024"
```

Formats a date string for display.

**Parameters:**
- `dateStr` (string): YYYY-MM-DD format

**Returns:** `string` - Formatted date

### getDayPlan(date)

```javascript
const todayPlan = Helpers.getDayPlan();
const specificPlan = Helpers.getDayPlan('2024-01-15');
```

Gets or creates a day plan for the specified date.

**Parameters:**
- `date` (string, optional): YYYY-MM-DD (defaults to today)

**Returns:** `Object` - Day plan object

### getWeeklyStats()

```javascript
const stats = Helpers.getWeeklyStats();
// Returns: { completed: 5, total: 7, percentage: 71 }
```

Calculates weekly completion statistics.

**Returns:** `Object`
- `completed` (number): Days with goals met
- `total` (number): Total days tracked
- `percentage` (number): Completion percentage

### getDailyProgress()

```javascript
const progress = Helpers.getDailyProgress();
// Returns: { overall: 65, breakdown: [...] }
```

Calculates daily progress across all categories.

**Returns:** `Object`
- `overall` (number): Overall percentage
- `breakdown` (Array): Category breakdowns

### calculateStreak()

```javascript
const streak = Helpers.calculateStreak();
// Returns: 7 (consecutive days)
```

Calculates the current streak of productive days.

**Returns:** `number` - Streak count

### logActivity(type, description, details)

```javascript
Helpers.logActivity(
  'task_completed',
  'Completed A-Z Task: A - Project Alpha',
  { taskId: 'abc123' }
);
```

Adds an entry to the activity timeline.

**Parameters:**
- `type` (string): Activity type identifier
- `description` (string): Human-readable description
- `details` (Object, optional): Additional metadata

### saveProgressSnapshot()

```javascript
Helpers.saveProgressSnapshot();
```

Saves current day's progress for historical tracking.

---

## ScreenRenderers Object

Functions that return HTML strings for each screen.

### Home()

```javascript
const html = ScreenRenderers.Home();
```

Renders the dashboard overview with quick stats and shortcuts.

### Daily()

```javascript
const html = ScreenRenderers.Daily();
```

Renders the daily planning view with day type, time blocks, goals, and routines.

### AtoZ()

```javascript
const html = ScreenRenderers.AtoZ();
```

Renders the A-Z task list with filtering and search.

### Journal()

```javascript
const html = ScreenRenderers.Journal();
```

Renders journal entries with type filtering.

### Routines()

```javascript
const html = ScreenRenderers.Routines();
```

Renders routine management and daily completion tracking.

### FocusAreas()

```javascript
const html = ScreenRenderers.FocusAreas();
```

Renders focus area tracking.

### EightSteps()

```javascript
const html = ScreenRenderers.EightSteps();
```

Renders the 8 Steps to Success checklist.

### Statistics()

```javascript
const html = ScreenRenderers.Statistics();
```

Renders analytics and progress charts.

### Reflections()

```javascript
const html = ScreenRenderers.Reflections();
```

Renders periodic reflection entries.

### Timeline()

```javascript
const html = ScreenRenderers.Timeline();
```

Renders activity history log.

### Settings()

```javascript
const html = ScreenRenderers.Settings();
```

Renders application settings.

---

## CognitiveController Object

Cognitive system for mode-based productivity governance.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `payload` | Object/null | Loaded cognitive state data |
| `initialized` | boolean | Whether init has been called |
| `error` | string/null | Last error message |
| `mode` | string | Current mode (BUILD/MAINTENANCE/CLOSURE) |
| `risk` | string | Current risk level (LOW/MEDIUM/HIGH) |

### init()

```javascript
await CognitiveController.init();
```

Loads cognitive state from `cognitive_state.json` and applies governance rules.

### retry()

```javascript
await CognitiveController.retry();
```

Resets and re-initializes the cognitive system.

### getMode()

```javascript
const mode = CognitiveController.getMode();
// Returns: 'BUILD' | 'MAINTENANCE' | 'CLOSURE' | 'OFFLINE'
```

Gets the current cognitive mode.

### getRisk()

```javascript
const risk = CognitiveController.getRisk();
// Returns: 'LOW' | 'MEDIUM' | 'HIGH' | 'UNKNOWN'
```

Gets the current risk level.

### getOpenLoops()

```javascript
const loops = CognitiveController.getOpenLoops();
// Returns: [{ title: 'Open task', ... }, ...]
```

Gets the list of open loops from cognitive state.

### isClosureMode()

```javascript
if (CognitiveController.isClosureMode()) {
  // Show closure warnings
}
```

Checks if currently in closure mode.

**Returns:** `boolean`

---

## Global Functions

Action handlers available in the global scope.

### Navigation

#### navigate(screen)

```javascript
navigate('Daily');
navigate('AtoZ');
```

Changes the current screen and re-renders.

**Parameters:**
- `screen` (string): Screen name matching ScreenRenderers key

#### render()

```javascript
render();
```

Re-renders the current screen and updates navigation.

### Task Management

#### createTask()

Called from modal to create a new A-Z task.

#### updateTask(id)

```javascript
updateTask('abc123');
```

Updates an existing task from modal inputs.

#### deleteTask(id)

```javascript
deleteTask('abc123');
```

Deletes a task after confirmation.

#### completeTask(id)

```javascript
completeTask('abc123');
```

Marks a task as completed.

#### filterTasks(status)

```javascript
filterTasks('completed');
filterTasks('in-progress');
filterTasks('not-started');
filterTasks('all');
```

Filters the task list by status.

#### searchTasks(query)

```javascript
searchTasks('project');
```

Searches tasks by query (debounced).

### Daily Planning

#### setDayType(type, applyTemplate)

```javascript
setDayType('A');           // Shows template modal
setDayType('B', true);     // Applies template
setDayType('C', false);    // Just changes type
```

Sets the day type and optionally applies template.

#### addTimeBlock()

Adds a new time block to today's plan.

#### toggleTimeBlockCompletion(id)

```javascript
toggleTimeBlockCompletion('block123');
```

Toggles a time block's completion status.

#### saveGoals()

Saves the baseline and stretch goals from form inputs.

#### toggleGoalCompletion(type)

```javascript
toggleGoalCompletion('baseline');
toggleGoalCompletion('stretch');
```

Toggles goal completion status.

### Routine Management

#### addNewRoutineType()

Opens modal to create a new routine category.

#### createNewRoutine()

Creates routine from modal inputs.

#### deleteRoutineType(name)

```javascript
deleteRoutineType('Morning');
```

Deletes a routine category after confirmation.

#### addRoutineStep(routineName)

```javascript
addRoutineStep('Morning');
```

Adds a new step to a routine.

#### toggleRoutineStep(routineName, stepIndex, completed)

```javascript
toggleRoutineStep('Morning', 0, true);
```

Toggles a routine step's completion.

#### toggleRoutineComplete(routineName)

```javascript
toggleRoutineComplete('Morning');
```

Toggles entire routine completion.

### Journal

#### openJournalModal(entryId, entryType)

```javascript
openJournalModal();                    // New free entry
openJournalModal(null, 'weekly');      // New weekly review
openJournalModal('j123');              // Edit existing
```

Opens journal entry modal.

#### saveJournalEntry(entryId)

Saves journal entry from modal inputs.

#### deleteJournalEntry(entryId)

```javascript
deleteJournalEntry('j123');
```

Deletes a journal entry after confirmation.

### Data Management

#### exportState()

Downloads a JSON backup of all data.

#### showImportModal()

Opens the import file dialog.

#### handleFileImport(event)

Processes an imported backup file.

#### clearData()

Deletes all data after confirmation.

#### resetToDefaults()

Resets settings to defaults after confirmation.

### Settings

#### toggleDarkMode()

Toggles dark mode on/off.

#### toggleSetting(setting)

```javascript
toggleSetting('autoSave');
toggleSetting('showProgress');
```

Toggles a boolean setting.

#### updateSetting(setting, value)

```javascript
updateSetting('theme', 'dark');
```

Updates a setting to a specific value.

### Cognitive System

#### toggleCognitiveBanner()

Toggles the cognitive directive banner visibility.

#### openControlPanel()

Opens the cognitive control panel in a new tab.

---

## AIContext Object

Context generation for AI agents. Located in `js/ai-context.js`.

### getContext()

```javascript
const context = AIContext.getContext();
```

Returns a comprehensive context snapshot including:
- `_meta` - Generation timestamp and version
- `temporal` - Current date/time information
- `navigation` - Current screen and available screens
- `todayPlan` - Day type, goals, time blocks, routines
- `progress` - Overall progress, breakdown, streak, weekly average
- `tasks` - All tasks with summary and groupings by status
- `routines` - Definitions and today's completion status
- `focusAreas` - Areas with task summaries
- `journal` - Recent entries and counts by type
- `history` - Recent activity and completed tasks
- `weeklyStats` - Weekly goal completion stats
- `cognitive` - Mode, risk level, open loops

**Returns:** `Object` - Full context snapshot

### getQuickContext()

```javascript
const quick = AIContext.getQuickContext();
// Returns: { today, dayType, overallProgress, tasksInProgress, pendingTimeBlocks, cognitiveMode, streak }
```

Returns a minimal context for quick queries.

**Returns:** `Object` - Condensed context

### getSystemPrompt()

```javascript
const prompt = AIContext.getSystemPrompt();
```

Generates a system prompt for LLMs with embedded current context.

**Returns:** `string` - Formatted system prompt

### getClipboardSnapshot()

```javascript
const markdown = AIContext.getClipboardSnapshot();
```

Generates a human-readable markdown snapshot optimized for pasting into LLM chats.

**Returns:** `string` - Markdown formatted context

### copyToClipboard(format)

```javascript
await AIContext.copyToClipboard('markdown');
await AIContext.copyToClipboard('json');
await AIContext.copyToClipboard('prompt');
```

Copies context to clipboard in the specified format.

**Parameters:**
- `format` (string): 'markdown' | 'json' | 'prompt'

**Returns:** `Promise<boolean>` - Success status

---

## AIActions Object

Action interface for AI agents. Located in `js/ai-actions.js`.

All methods return `{ success: boolean, ...data }` or `{ success: false, error/errors }`.

### Task Management

#### createTask(letter, taskText, notes)

```javascript
const result = AIActions.createTask('C', 'Review weekly goals', 'AI suggestion');
// Returns: { success: true, taskId: '...', task: {...} }
```

Creates a new A-Z task.

#### completeTask(taskId)

```javascript
const result = AIActions.completeTask('abc123');
```

Marks a task as completed.

#### updateTaskStatus(taskId, status)

```javascript
const result = AIActions.updateTaskStatus('abc123', TASK_STATUS.IN_PROGRESS);
```

Updates a task's status.

#### updateTask(taskId, updates)

```javascript
const result = AIActions.updateTask('abc123', { task: 'New text', notes: 'New notes' });
```

Updates task text and/or notes.

#### findTaskByLetter(letter)

```javascript
const task = AIActions.findTaskByLetter('A');
```

Finds a task by its letter.

**Returns:** `Object|null` - Task object or null

### Day Planning

#### setDayType(type, applyTemplate)

```javascript
AIActions.setDayType('A');         // Just change type
AIActions.setDayType('B', true);   // Apply template
```

Sets today's day type.

#### setGoals(baseline, stretch)

```javascript
AIActions.setGoals('Complete 3 tasks', 'Review progress');
```

Sets daily baseline and/or stretch goals.

#### toggleGoal(goalType)

```javascript
AIActions.toggleGoal('baseline');  // or 'stretch'
```

Toggles goal completion status.

### Time Blocks

#### addTimeBlock(time, title, duration)

```javascript
AIActions.addTimeBlock('9:00 AM', 'Deep Work', 90);
```

Adds a time block to today's plan.

#### toggleTimeBlock(blockId)

```javascript
AIActions.toggleTimeBlock('block123');
```

Toggles time block completion.

#### deleteTimeBlock(blockId)

```javascript
AIActions.deleteTimeBlock('block123');
```

Removes a time block.

### Routines

#### completeRoutineStep(routineName, stepIndex)

```javascript
AIActions.completeRoutineStep('Morning', 0);
```

Marks a routine step as complete.

#### completeRoutine(routineName)

```javascript
AIActions.completeRoutine('Morning');
```

Marks entire routine as complete.

### Journal

#### addJournalEntry(title, content, entryType, mood)

```javascript
AIActions.addJournalEntry('Daily Reflection', 'Content here...', 'free', '😊');
```

Creates a journal entry.

**Parameters:**
- `title` (string): Entry title (max 200 chars)
- `content` (string): Entry content (max 5000 chars)
- `entryType` (string): 'free' | 'weekly' | 'gratitude'
- `mood` (string, optional): Emoji mood indicator

### Momentum Wins

#### addMomentumWin(description)

```javascript
AIActions.addMomentumWin('Finished report ahead of schedule!');
```

Logs a quick win.

### Navigation

#### navigateTo(screen)

```javascript
AIActions.navigateTo('Statistics');
```

Navigates to a screen.

**Valid screens:** Home, Daily, AtoZ, Journal, Routines, FocusAreas, EightSteps, Statistics, Reflections, Timeline, Settings

### Suggestions

#### suggestDayType()

```javascript
const suggestion = AIActions.suggestDayType();
// Returns: { suggestion: 'A', reasoning: '...', metrics: { streak, weeklyAverage, cognitiveMode } }
```

Suggests optimal day type based on history and cognitive state.

#### suggestNextAction()

```javascript
const actions = AIActions.suggestNextAction();
// Returns: [{ priority, action, details, method }, ...]
```

Returns prioritized list of suggested next actions.

### Context

#### getContext()

```javascript
const ctx = AIActions.getContext();
```

Alias for `AIContext.getContext()`.

#### getQuickContext()

```javascript
const quick = AIActions.getQuickContext();
```

Alias for `AIContext.getQuickContext()`.

---

## Global Functions (AI)

### showCopyContextModal()

```javascript
showCopyContextModal();
```

Opens the modal to copy AI context in various formats.
