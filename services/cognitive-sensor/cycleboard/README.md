# CycleBoard - in-PACT Self-Sustaining Bullet Journal

A feature-rich, browser-based bullet journal application for planning, tracking, and reviewing A-Z monthly goals with cognitive state management.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Architecture](#architecture)
- [Modules](#modules)
- [State Management](#state-management)
- [Data Persistence](#data-persistence)
- [Accessibility](#accessibility)
- [Customization](#customization)

---

## Overview

CycleBoard is a productivity application that combines traditional bullet journaling with modern web technologies. It helps users:

- Plan daily activities with A/B/C day types
- Track A-Z monthly tasks
- Manage routines and time blocks
- Journal thoughts and reflections
- Monitor progress with statistics and timelines

## Features

### Core Features

| Feature | Description |
|---------|-------------|
| **A-Z Tasks** | 26 lettered monthly goals (A through Z) with status tracking |
| **Daily Planning** | Day type system (A/B/C) with customizable templates |
| **Time Blocks** | Schedule-based task management |
| **Routines** | Repeatable routine checklists (Morning, Evening, etc.) |
| **Journal** | Free-form, weekly review, and gratitude entries |
| **Reflections** | Weekly, monthly, quarterly, and yearly reviews |
| **Statistics** | Progress tracking and analytics |
| **Timeline** | Activity history log |

### Additional Features

- **Dark Mode** - Toggle between light and dark themes
- **Data Export/Import** - Backup and restore functionality
- **Keyboard Shortcuts** - Ctrl+S (save), Ctrl+E (export), Ctrl+Z (undo)
- **Undo/Redo** - Up to 50 history states
- **Cognitive System** - Optional brain integration for mode-based governance
- **Mobile Responsive** - Works on desktop and mobile devices
- **AI Integration** - Copy context snapshots to share with any LLM

---

## Project Structure

```
cycleboard/
├── index.html              # Main HTML entry point
├── cognitive_state.json    # Cognitive system configuration (optional)
├── css/
│   └── styles.css          # Custom styles and animations
└── js/
    ├── state.js            # State management and persistence
    ├── validator.js        # Data validation utilities
    ├── ui.js               # UI components (toasts, modals, loading)
    ├── helpers.js          # Utility functions
    ├── screens.js          # Screen/view renderers
    ├── functions.js        # Action handlers and business logic
    ├── cognitive.js        # Cognitive system controller
    ├── ai-context.js       # AI context generation (LLM integration)
    ├── ai-actions.js       # AI action interface (LLM integration)
    └── app.js              # Application initialization
```

---

## Getting Started

### Prerequisites

- Modern web browser (Chrome, Firefox, Safari, Edge)
- Local web server (for cognitive system features)

### Installation

1. Clone or copy the `cycleboard` folder to your workspace
2. Open `index.html` in a browser, or serve via a local server:

```bash
# Using Python
python -m http.server 8000

# Using Node.js
npx serve .

# Using PHP
php -S localhost:8000
```

3. Navigate to `http://localhost:8000`

### First Use

1. The app initializes with default state
2. Navigate using the sidebar (desktop) or bottom nav (mobile)
3. Create your first A-Z task from the Home or A-Z screen
4. Set your day type and configure routines

---

## Architecture

### Module Loading Order

```
1. state.js       - Constants and CycleBoardState class
2. validator.js   - DataValidator class
3. ui.js          - UI utilities object
4. helpers.js     - Helpers object
5. screens.js     - ScreenRenderers object
6. functions.js   - Action functions
7. cognitive.js   - CognitiveController object
8. ai-context.js  - AIContext object (LLM integration)
9. ai-actions.js  - AIActions object (LLM integration)
10. app.js        - Initialization
```

### Global Objects

| Object | Purpose |
|--------|---------|
| `stateManager` | CycleBoardState instance for state operations |
| `state` | Getter/setter for current application state |
| `UI` | Toast, modal, and loading utilities |
| `Helpers` | Date formatting, progress calculation utilities |
| `ScreenRenderers` | HTML generators for each screen |
| `CognitiveController` | Cognitive system integration |
| `DataValidator` | Input and import validation |
| `AIContext` | Context generation for LLM integration |
| `AIActions` | Action interface for AI agents |

### Constants

```javascript
// Task statuses
TASK_STATUS.NOT_STARTED  // 'Not Started'
TASK_STATUS.IN_PROGRESS  // 'In Progress'
TASK_STATUS.COMPLETED    // 'Completed'

// Day types
DAY_TYPE.A  // Optimal day
DAY_TYPE.B  // Low energy day
DAY_TYPE.C  // Chaos/survival day

// Reflection periods
REFLECTION_PERIOD.WEEKLY
REFLECTION_PERIOD.MONTHLY
REFLECTION_PERIOD.QUARTERLY
REFLECTION_PERIOD.YEARLY
```

---

## Modules

### state.js

Handles application state management.

```javascript
class CycleBoardState {
  constructor()           // Initialize state from storage
  loadFromStorage()       // Load from localStorage
  saveToStorage()         // Persist to localStorage (debounced)
  update(changes)         // Merge changes and save
  undo()                  // Revert to previous state
  redo()                  // Re-apply undone state
  generateId()            // Create unique IDs
  getTodayDate()          // Get YYYY-MM-DD string
  getDefaultState()       // Return fresh state object
}
```

### validator.js

Validates user input and imported data.

```javascript
class DataValidator {
  static validateTask(task)           // Validate A-Z task
  static validateDayPlan(plan)        // Validate day plan
  static validateJournalEntry(entry)  // Validate journal entry
  static validateRoutineStep(step)    // Validate routine step
  static validateImportData(data)     // Validate backup file
  static migrateImportData(data, defaults)  // Fill missing fields
}
```

### ui.js

UI component utilities.

```javascript
const UI = {
  sanitize(input)              // Escape HTML for XSS prevention
  showToast(title, desc, type) // Display notification
  showModal(content)           // Open modal dialog
  closeModal()                 // Close modal
  showLoading(message)         // Show loading overlay
  hideLoading()                // Hide loading overlay
  spinnerHtml(size)            // Get spinner HTML
  getColorClass(color, type)   // Get Tailwind color class
  renderProgressRing(pct)      // SVG progress ring
  updateDateDisplay()          // Update header date
}
```

### helpers.js

Utility functions.

```javascript
const Helpers = {
  formatDate(dateStr)          // Format date for display
  getDayPlan(date)             // Get/create day plan
  getWeeklyStats()             // Calculate weekly statistics
  getDailyProgress()           // Calculate daily completion
  calculateStreak()            // Calculate consecutive days
  logActivity(type, desc, details)  // Add to timeline
  saveProgressSnapshot()       // Save daily progress
}
```

### screens.js

Screen renderers returning HTML strings.

```javascript
const ScreenRenderers = {
  Home()          // Dashboard overview
  Daily()         // Daily planning view
  AtoZ()          // A-Z task list
  Journal()       // Journal entries
  Routines()      // Routine management
  FocusAreas()    // Focus area tracking
  EightSteps()    // 8 Steps to Success
  Statistics()    // Analytics dashboard
  Reflections()   // Review entries
  Timeline()      // Activity history
  Settings()      // App configuration
}
```

### functions.js

Action handlers and business logic.

Key functions:

```javascript
// Navigation
navigate(screen)              // Change current screen
render()                      // Re-render current screen

// Tasks
createTask()                  // Create A-Z task
updateTask(id)                // Update task
deleteTask(id)                // Delete task
completeTask(id)              // Mark task complete
filterTasks(status)           // Filter task list
searchTasks(query)            // Search tasks

// Daily Planning
setDayType(type)              // Set A/B/C day type
addTimeBlock()                // Add time block
toggleTimeBlockCompletion(id) // Toggle block done
saveGoals()                   // Save daily goals

// Routines
addNewRoutineType()           // Create routine category
addRoutineStep(name)          // Add step to routine
toggleRoutineStep(name, idx)  // Toggle step completion

// Data Management
exportState()                 // Download backup JSON
showImportModal()             // Show import dialog
handleFileImport(event)       // Process import file
clearData()                   // Reset all data
```

### cognitive.js

Cognitive system for mode-based productivity governance.

```javascript
const CognitiveController = {
  init()              // Load cognitive_state.json
  retry()             // Retry initialization
  applyGovernance()   // Apply mode-based rules
  getMode()           // Get current mode (BUILD/MAINTENANCE/CLOSURE)
  getRisk()           // Get risk level (LOW/MEDIUM/HIGH)
  getOpenLoops()      // Get open loop items
  isClosureMode()     // Check if in closure mode
}
```

### ai-context.js

Context generation for AI/LLM integration.

```javascript
const AIContext = {
  getContext()           // Full application state snapshot
  getQuickContext()      // Minimal context for quick queries
  getSystemPrompt()      // Generate LLM system prompt
  getClipboardSnapshot() // Human-readable markdown snapshot
  copyToClipboard(fmt)   // Copy to clipboard ('markdown'|'json'|'prompt')
}
```

### ai-actions.js

Action interface for AI agents to modify state.

```javascript
const AIActions = {
  // Tasks
  createTask(letter, text, notes)
  completeTask(id)
  updateTaskStatus(id, status)

  // Day Planning
  setDayType(type, applyTemplate)
  setGoals(baseline, stretch)
  addTimeBlock(time, title, duration)

  // Routines
  completeRoutineStep(name, index)
  completeRoutine(name)

  // Journal
  addJournalEntry(title, content, type)

  // Suggestions
  suggestDayType()      // AI-powered day type suggestion
  suggestNextAction()   // Prioritized action list
}
```

### app.js

Application initialization.

```javascript
// Creates stateManager instance
// Defines state getter/setter on window
// Initializes app on DOMContentLoaded
// Initializes cognitive controller
```

---

## State Management

### State Structure

```javascript
{
  screen: 'Home',                    // Current screen
  AZTask: [],                        // A-Z task array
  DayPlans: {},                      // Date-keyed day plans
  DayTypeTemplates: {},              // A/B/C day templates
  Routine: {},                       // Routine definitions
  Journal: [],                       // Journal entries
  FocusArea: [],                     // Focus areas
  EightSteps: {},                    // Daily 8-step tracking
  Contingencies: {},                 // Emergency protocols
  MomentumWins: [],                  // Quick wins log
  Reflections: {},                   // Period reflections
  History: {                         // Activity history
    completedTasks: [],
    timeline: []
  },
  Settings: {                        // User preferences
    darkMode: false,
    autoSave: true,
    showProgress: true
  },
  UI: {                              // UI state
    azFilter: 'all',
    azSearch: ''
  }
}
```

### State Updates

```javascript
// Direct mutation (will be saved)
state.Settings.darkMode = true;
stateManager.update({ Settings: state.Settings });

// Or use the update method
stateManager.update({
  Settings: { ...state.Settings, darkMode: true }
});
```

### Undo/Redo

```javascript
stateManager.undo();  // Ctrl+Z
stateManager.redo();  // Ctrl+Shift+Z
```

---

## Data Persistence

### Storage

Data is persisted to `localStorage` under the key `cycleboard-state`.

### Backup/Restore

Export creates a timestamped JSON file:
```
cycleboard-backup-2024-01-15.json
```

Import validates and migrates data from older versions automatically.

### Auto-Save

- Changes are debounced (500ms) before saving
- Backup save every 5 minutes
- Save on page unload

---

## Accessibility

The application includes:

- **ARIA Labels** - All interactive elements have proper labels
- **Keyboard Navigation** - Tab through elements, Escape to close modals
- **Focus Management** - Focus is trapped in modals and restored on close
- **Screen Reader Support** - Live regions for toasts, proper roles for dialogs
- **Color Contrast** - Dark mode with appropriate contrast ratios

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+S` | Save data |
| `Ctrl+E` | Export backup |
| `Ctrl+N` / `Ctrl+K` | Quick add (context-aware) |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` | Redo |
| `Escape` | Close modal |

---

## Customization

### Day Type Templates

Edit templates via Daily screen > Day Mode > Edit button:

- **A-Day (Optimal)**: Full energy, maximum output
- **B-Day (Low Energy)**: Conserve energy, essentials only
- **C-Day (Chaos)**: Survival mode, one priority

### Routines

Create custom routines from the Routines screen:

1. Click "Add New Routine"
2. Enter routine name
3. Add steps to the routine
4. Reorder steps with up/down arrows

### Themes

Toggle dark mode via:
- Header moon icon (mobile)
- Settings screen toggle (desktop)
- Keyboard: Update Settings.darkMode

---

## Browser Support

| Browser | Minimum Version |
|---------|-----------------|
| Chrome | 80+ |
| Firefox | 75+ |
| Safari | 13+ |
| Edge | 80+ |

---

## License

This project is for personal use. All rights reserved.

---

## Troubleshooting

### Data Not Saving

1. Check if localStorage is available
2. Check browser privacy settings
3. Try exporting data and clearing localStorage

### Cognitive System Offline

The cognitive banner requires:
1. A valid `cognitive_state.json` file
2. Running from a web server (not file://)

### Import Failing

1. Ensure the file is valid JSON
2. Check browser console for specific errors
3. The file must have been exported from CycleBoard

---

## Contributing

To extend the application:

1. Add new screens to `ScreenRenderers` in `screens.js`
2. Add navigation items in the `render()` function
3. Add action handlers in `functions.js`
4. Update state structure in `stateManager.getDefaultState()`
5. Add validation in `DataValidator`
