# CycleBoard App Skeleton

## File Structure
```
cycleboard_app3.html (Single-file application)
├── HTML Structure
├── CSS/Tailwind Styles
└── JavaScript Application
```

---

## HTML Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Meta tags, Tailwind CSS, Font Awesome -->
</head>
<body>
  <div id="app">
    <!-- Sidebar Navigation -->
    <aside id="sidebar">
      <div id="nav"></div>  <!-- Dynamic navigation -->
    </aside>

    <!-- Main Content Area -->
    <main id="main-content">
      <div class="max-w-6xl"></div>  <!-- Screen content rendered here -->
    </main>
  </div>

  <!-- Modal Container -->
  <div id="modal"></div>

  <!-- Toast Notifications -->
  <div id="toast-container"></div>
</body>
</html>
```

---

## State Management

```javascript
const stateManager = {
  state: {},
  undoStack: [],
  redoStack: [],

  getDefaultState() {
    return {
      screen: 'Home',

      // Core Data
      AZTask: [],           // A-Z goal tracker tasks
      FocusArea: [],        // PigPen/Weekly focus areas (6 categories)
      DayPlans: {},         // Daily plans keyed by date
      Routine: {},          // Routine templates (Morning, Commute, Evening)
      Journal: [],          // Journal entries

      // New Features
      EightSteps: {},       // 8 Steps to Success tracking per day
      Contingencies: {},    // Contingency plan actions
      Reflections: {},      // Weekly/Monthly/Quarterly/Yearly reflections
      MomentumWins: [],     // Small wins log

      // System
      Settings: {},         // User preferences
      History: {}           // Activity timeline, streaks
    };
  },

  // Methods
  loadFromStorage(),
  saveToStorage(),
  update(changes),
  undo(),
  redo(),
  generateId(),
  getTodayDate()
};
```

---

## Navigation Screens

```javascript
const screens = [
  { id: 'Home',        label: 'Home',         icon: 'fa-home' },
  { id: 'Daily',       label: 'Daily',        icon: 'fa-calendar-day' },
  { id: 'AtoZ',        label: 'A–Z',          icon: 'fa-tasks' },
  { id: 'WeeklyFocus', label: 'Weekly Focus', icon: 'fa-bullseye' },
  { id: 'Reflections', label: 'Reflections',  icon: 'fa-lightbulb' },
  { id: 'Timeline',    label: 'Timeline',     icon: 'fa-history' },
  { id: 'Routines',    label: 'Routines',     icon: 'fa-clock' },
  { id: 'Journal',     label: 'Journal',      icon: 'fa-book' },
  { id: 'Statistics',  label: 'Statistics',   icon: 'fa-chart-line' },
  { id: 'Settings',    label: 'Settings',     icon: 'fa-cog' }
];
```

---

## Screen Renderers

```javascript
const ScreenRenderers = {

  Home() {
    // Dashboard with:
    // - Today's progress ring
    // - Quick actions grid
    // - Productivity streak tracker
    // - 7-day progress history
    // - Today's routines summary
    // - Momentum wins tracker
    // - Recent A-Z tasks
  },

  Daily() {
    // Daily planning with:
    // - Day type selector (A/B/C)
    // - Progress overview
    // - Time blocks manager
    // - Baseline (X) & Stretch (Y) goals
    // - 8 Steps to Success widget
    // - Contingency quick actions
    // - Yesterday's reflection
  },

  AtoZ() {
    // A-Z task manager with:
    // - Search and filter
    // - Task cards (A-Z)
    // - Status tracking
    // - CRUD operations
  },

  WeeklyFocus() {
    // PigPen goals (6 areas):
    // - Production, Image, Growth
    // - Personal, Errands, Network
    // - Tasks per area
    // - Focus distribution chart
  },

  Reflections() {
    // Reflection cycles:
    // - Weekly tab
    // - Monthly tab
    // - Quarterly tab
    // - Yearly tab
    // - Structured prompts per type
  },

  Timeline() {
    // Activity history:
    // - Chronological activity log
    // - Grouped by date
    // - Export functionality
  },

  Routines() {
    // Routine management:
    // - Today's routine tracker
    // - Routine templates (Morning, Commute, Evening, etc.)
    // - Step management
    // - Progress tracking
  },

  Journal() {
    // Journal entries:
    // - Entry types (Free, Weekly Review, Gratitude)
    // - Mood tracking
    // - Tags
    // - Linked tasks
  },

  Statistics() {
    // Analytics:
    // - Monthly task completion
    // - Active days
    // - Weekly success rate
    // - Task status distribution
    // - Day type usage
    // - Recent activity
  },

  Settings() {
    // Preferences:
    // - Dark mode toggle
    // - Notifications
    // - Auto-save
    // - Default day type
    // - Data management (export/import/clear)
  }
};
```

---

## Helper Functions

```javascript
const Helpers = {
  // Date helpers
  getTodayDate(),
  formatDate(date),
  getYesterday(),

  // Day plan helpers
  getDayPlan(),
  createDefaultDayPlan(date),

  // Progress calculations
  calculateDailyProgress(),
  getProgressStreak(),
  getProgressHistory(days),
  getAverageProgress(days),
  getWeeklyStats(),

  // Activity logging
  logActivity(type, description, details),
  saveProgressSnapshot()
};
```

---

## UI Utilities

```javascript
const UI = {
  showModal(content),
  closeModal(),
  showToast(title, message, type),
  updateDateDisplay(),
  sanitize(text)
};
```

---

## Core Functions

### Task Management
```javascript
createTask()
updateTask(id)
deleteTask(id)
completeTask(id)
filterTasks(status)
searchTasks(query)
sortTasks()
```

### Daily Planning
```javascript
setDayType(type)           // A, B, or C day
addTimeBlock()
updateTimeBlock(id, field, value)
removeTimeBlock(id)
toggleTimeBlockCompletion(id)
saveGoals()
toggleGoalCompletion(type) // baseline or stretch
```

### 8 Steps to Success
```javascript
toggleEightStep(stepId)
```

### Contingencies
```javascript
activateContingency(type)  // runningLate, lowEnergy, freeTime, disruption
applyContingency(type)
```

### Routines
```javascript
addNewRoutineType()
createNewRoutine()
deleteRoutineType(name)
addRoutineStep(routineName)
updateRoutineStep(routineName, index, value)
deleteRoutineStep(routineName, index)
moveRoutineStep(routineName, index, direction)
toggleRoutineStep(routineName, stepIndex, completed)
toggleRoutineComplete(routineName)
```

### Focus Areas (PigPen)
```javascript
addFocusTask(areaId)
createFocusTask(areaId)
toggleFocusTask(areaId, taskId)
removeFocusTask(areaId, taskId)
```

### Journal
```javascript
openJournalModal(entryId, entryType)
saveJournalEntry(entryId)
editJournalEntry(entryId)
deleteJournalEntry(entryId)
switchJournalType(type, entryId)
```

### Reflections
```javascript
openReflectionModal(type)  // weekly, monthly, quarterly, yearly
saveReflection(type)
deleteReflection(type, reflectionId)
setReflectionTab(tab)
```

### Momentum Wins
```javascript
addMomentumWin()
saveMomentumWin()
deleteMomentumWin(winId)
```

### Data Management
```javascript
exportState()
showImportModal()
handleFileImport(event)
clearData()
resetToDefaults()
toggleSetting(setting)
updateSetting(setting, value)
toggleDarkMode()
```

### Navigation & Rendering
```javascript
navigate(screen)
render()
renderNav()
init()
```

---

## Data Structures

### AZTask
```javascript
{
  id: string,
  letter: 'A' - 'Z',
  task: string,
  notes: string,
  status: 'Not Started' | 'In Progress' | 'Completed',
  createdAt: ISO string
}
```

### FocusArea (PigPen)
```javascript
{
  id: string,
  name: 'Production' | 'Image' | 'Growth' | 'Personal' | 'Errands' | 'Network',
  definition: string,
  color: hex string,
  tasks: [{ id, text, completed, createdAt }]
}
```

### DayPlan
```javascript
{
  date: 'YYYY-MM-DD',
  day_type: 'A' | 'B' | 'C',
  time_blocks: [{ id, time, title, completed }],
  baseline_goal: { text, completed },
  stretch_goal: { text, completed },
  notes: string,
  routines_completed: { [routineName]: { completed, steps: {} } },
  progress_snapshots: [{ timestamp, progress }]
}
```

### Routine
```javascript
{
  [routineName]: string[]  // Array of step descriptions
}
// Default: Morning, Commute, Evening
```

### Journal Entry
```javascript
{
  id: string,
  title: string,
  content: string,
  tags: string[],
  mood: emoji string,
  linkedTasks: string[],
  entryType: 'free' | 'weekly' | 'gratitude',
  timestamp: ISO string,
  createdAt: ISO string,
  updatedAt: ISO string
}
```

### Reflection
```javascript
{
  id: string,
  type: 'weekly' | 'monthly' | 'quarterly' | 'yearly',
  timestamp: ISO string,
  mood: string,
  responses: { [promptId]: string }
}
```

### MomentumWin
```javascript
{
  id: string,
  text: string,
  timestamp: ISO string,
  date: 'YYYY-MM-DD'
}
```

### EightSteps (per day)
```javascript
{
  'YYYY-MM-DD': {
    positiveAttitude: boolean,
    beOnTime: boolean,
    bePrepared: boolean,
    workFullDay: boolean,
    workTerritory: boolean,
    greatAttitude: boolean,
    knowWhy: boolean,
    takeControl: boolean
  }
}
```

### Settings
```javascript
{
  darkMode: boolean,
  notifications: boolean,
  autoSave: boolean,
  defaultDayType: 'A' | 'B' | 'C'
}
```

### History
```javascript
{
  completedTasks: [{ taskId, completedAt }],
  productivityScore: number,
  streak: number,
  timeline: [{ id, type, description, details, timestamp }]
}
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| H | Navigate to Home |
| D | Navigate to Daily |
| A | Navigate to A-Z |
| W | Navigate to Weekly Focus |
| T | Navigate to Timeline |
| R | Navigate to Routines |
| S | Navigate to Statistics |
| Q | Open Quick Entry modal |
| ? | Show keyboard shortcuts |
| Esc | Close modal |
| Ctrl+S | Save data |
| Ctrl+E | Export data |
| Ctrl+K/N | New task/block |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |

---

## Technology Stack

- **HTML5**: Single-page structure
- **Tailwind CSS**: Utility-first styling (via CDN)
- **Font Awesome**: Icons (via CDN)
- **Vanilla JavaScript**: No framework dependencies
- **localStorage**: Data persistence
- **No backend**: Fully client-side application
