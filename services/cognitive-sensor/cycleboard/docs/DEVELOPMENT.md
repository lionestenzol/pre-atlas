# CycleBoard Development Guide

Guide for extending and modifying the CycleBoard application.

---

## Table of Contents

1. [Development Setup](#development-setup)
2. [Code Style](#code-style)
3. [Adding New Features](#adding-new-features)
4. [Module Guidelines](#module-guidelines)
5. [Testing](#testing)
6. [Common Patterns](#common-patterns)
7. [Troubleshooting](#troubleshooting)

---

## Development Setup

### Prerequisites

- Text editor (VS Code recommended)
- Modern web browser with DevTools
- Local web server for cognitive features
- Git for version control

### Recommended VS Code Extensions

- Tailwind CSS IntelliSense
- ESLint
- Prettier
- Live Server

### Running Locally

```bash
# Using Python
cd cycleboard
python -m http.server 8000

# Using Node.js
npx serve .

# Using VS Code Live Server
# Right-click index.html > Open with Live Server
```

### Development Workflow

1. Make changes to source files
2. Refresh browser to see changes
3. Check browser console for errors
4. Test on both desktop and mobile viewports
5. Test dark mode
6. Verify data persistence (refresh page)

---

## Code Style

### JavaScript

```javascript
// Use const for constants and let for variables
const MAX_HISTORY = 50;
let currentIndex = 0;

// Use descriptive function names
function calculateDailyProgress() { ... }  // Good
function calc() { ... }                     // Bad

// Use arrow functions for callbacks
array.map(item => item.value);

// Use template literals for HTML
const html = `
  <div class="${className}">
    ${UI.sanitize(userInput)}
  </div>
`;

// Always sanitize user input
UI.sanitize(userInput);

// Use constants instead of magic strings
if (task.status === TASK_STATUS.COMPLETED) { ... }
```

### HTML in JavaScript

```javascript
// Always escape user data
const html = `
  <p>${UI.sanitize(entry.title)}</p>
  <input value="${UI.sanitize(entry.value)}" />
`;

// Use semantic HTML
'<button>' instead of '<div onclick>'
'<nav>' for navigation
'<main>' for main content
'<aside>' for sidebars

// Include ARIA labels
`<button aria-label="Delete task">
  <i class="fas fa-trash" aria-hidden="true"></i>
</button>`
```

### CSS/Tailwind

```html
<!-- Use Tailwind utility classes -->
<div class="flex items-center gap-4 p-4 rounded-lg">

<!-- Dark mode support -->
<div class="bg-white dark:bg-gray-800 text-black dark:text-white">

<!-- Responsive design -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3">

<!-- For dynamic colors, use UI.getColorClass() -->
<div class="${UI.getColorClass('blue', 'bg')}">
```

---

## Adding New Features

### 1. Adding a New Screen

**Step 1: Add the renderer in `screens.js`**

```javascript
const ScreenRenderers = {
  // ... existing screens ...

  NewScreen() {
    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <h1 class="text-3xl font-bold tracking-tight dark:text-white">New Screen</h1>
          <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Screen description</p>
        </div>

        <!-- Screen content -->
        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
          <h2 class="text-xl font-bold mb-4 dark:text-white">Section Title</h2>
          <!-- Content here -->
        </div>
      </div>
    `;
  }
};
```

**Step 2: Add navigation in `functions.js` (in the `render` function)**

Find the navigation items array and add:

```javascript
{ id: 'NewScreen', label: 'New Screen', icon: 'fa-star' }
```

**Step 3: Update mobile navigation in `index.html`** (if needed)

```html
<button onclick="navigate('NewScreen')" class="flex flex-col items-center p-2" aria-label="Go to New Screen">
  <i class="fas fa-star text-lg" aria-hidden="true"></i>
  <span class="text-xs mt-1">New</span>
</button>
```

### 2. Adding New State Properties

**Step 1: Update default state in `state.js`**

```javascript
getDefaultState() {
  return {
    // ... existing properties ...
    NewFeature: {
      items: [],
      settings: {}
    }
  };
}
```

**Step 2: Add migration in `validator.js`**

```javascript
static migrateImportData(data, defaults) {
  const migrated = { ...data };
  const migratedFeatures = [];

  // ... existing migrations ...

  if (!migrated.NewFeature) {
    migrated.NewFeature = defaults.NewFeature;
    migratedFeatures.push('NewFeature');
  }

  return { migrated, migratedFeatures };
}
```

### 3. Adding Action Functions

**In `functions.js`:**

```javascript
function createNewItem() {
  // Validate input
  const input = document.getElementById('new-item-input').value.trim();
  if (!input) {
    UI.showToast('Error', 'Input is required', 'error');
    return;
  }

  // Create item
  const newItem = {
    id: stateManager.generateId(),
    text: input,
    createdAt: new Date().toISOString()
  };

  // Update state
  state.NewFeature.items.push(newItem);
  stateManager.update({ NewFeature: state.NewFeature });

  // Log activity
  Helpers.logActivity('item_created', `Created item: ${input}`, { itemId: newItem.id });

  // Update UI
  UI.closeModal();
  render();
  UI.showToast('Success', 'Item created', 'success');
}
```

### 4. Adding Validation

**In `validator.js`:**

```javascript
static validateNewItem(item) {
  const errors = [];

  if (!item.text || item.text.trim() === '') {
    errors.push('Item text is required');
  }

  if (item.text && item.text.length > 500) {
    errors.push('Item text too long (max 500 characters)');
  }

  return errors;
}
```

### 5. Adding Constants

**In `state.js`:**

```javascript
const NEW_ITEM_STATUS = Object.freeze({
  PENDING: 'pending',
  ACTIVE: 'active',
  ARCHIVED: 'archived'
});
```

---

## Module Guidelines

### state.js

- Only state management logic
- No DOM manipulation
- No UI updates
- Export constants and CycleBoardState class

### validator.js

- Pure validation functions
- Return arrays of error strings
- No side effects
- No state modifications

### ui.js

- DOM manipulation for notifications/modals
- No business logic
- No direct state access
- Sanitize all user input

### helpers.js

- Utility functions
- Date formatting
- Statistics calculations
- Activity logging

### screens.js

- Only return HTML strings
- Use UI.sanitize() for user data
- Use constants for status values
- No state modifications
- No side effects

### functions.js

- Action handlers
- Business logic
- State updates
- Screen rendering orchestration

### cognitive.js

- Cognitive system only
- Isolated from core app
- Graceful degradation

### ai-context.js

- Context generation for AI/LLM integration
- Read-only operations
- No state modifications
- Returns structured data for AI consumption

### ai-actions.js

- Action interface for AI agents
- All methods return `{ success, ...data }` or `{ success: false, error }`
- Log all activities with `source: 'AI'`
- Validate inputs before state changes
- Show UI feedback via `UI.showToast()`

### app.js

- Initialization only
- No business logic
- Setup global objects

---

## Testing

### Manual Testing Checklist

#### State Persistence
- [ ] Create data, refresh page, verify data persists
- [ ] Export data, clear data, import, verify restoration
- [ ] Test undo/redo (Ctrl+Z, Ctrl+Shift+Z)

#### Navigation
- [ ] All screens load without errors
- [ ] Mobile navigation works
- [ ] Sidebar navigation works
- [ ] Deep linking (if applicable)

#### Data Operations
- [ ] Create items (tasks, journal entries, etc.)
- [ ] Edit items
- [ ] Delete items (with confirmation)
- [ ] Complete/toggle items

#### UI Components
- [ ] Modals open and close properly
- [ ] Escape key closes modals
- [ ] Focus management works
- [ ] Toasts appear and auto-dismiss
- [ ] Loading states appear during async operations

#### Accessibility
- [ ] Tab navigation works
- [ ] Screen reader announces notifications
- [ ] Color contrast is sufficient
- [ ] All buttons have accessible names

#### Responsive Design
- [ ] Desktop layout (>768px)
- [ ] Tablet layout
- [ ] Mobile layout (<768px)
- [ ] Bottom navigation on mobile

#### Dark Mode
- [ ] Toggle works
- [ ] Persists on refresh
- [ ] All components styled properly
- [ ] Sufficient contrast

### Console Checks

```javascript
// Check for errors
// Open DevTools Console and verify no errors on:
// - Page load
// - Navigation between screens
// - Data operations
// - Import/export

// Check state
console.log(state);
console.log(stateManager.history.length);

// Check localStorage
console.log(localStorage.getItem('cycleboard-state'));
```

---

## Common Patterns

### Modal Pattern

```javascript
function openMyModal(itemId = null) {
  const item = itemId ? findItem(itemId) : null;
  const isEdit = !!item;

  const content = `
    <div class="p-6">
      <h2 class="text-xl font-bold mb-4 dark:text-white">
        ${isEdit ? 'Edit' : 'Create'} Item
      </h2>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-1 dark:text-gray-300">Name</label>
          <input
            id="item-name"
            type="text"
            value="${item ? UI.sanitize(item.name) : ''}"
            class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2"
          />
        </div>
      </div>
      <div class="flex justify-end gap-3 mt-6">
        <button onclick="UI.closeModal()" class="px-4 py-2 border dark:border-gray-600 dark:text-gray-300 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700">
          Cancel
        </button>
        <button onclick="saveItem('${itemId || ''}')" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          ${isEdit ? 'Update' : 'Create'}
        </button>
      </div>
    </div>
  `;

  UI.showModal(content);
}
```

### Delete with Confirmation

```javascript
function deleteItem(id) {
  const item = state.Items.find(i => i.id === id);
  if (!item) return;

  if (confirm(`Delete "${item.name}"? This cannot be undone.`)) {
    state.Items = state.Items.filter(i => i.id !== id);
    stateManager.update({ Items: state.Items });
    Helpers.logActivity('item_deleted', `Deleted: ${item.name}`, { itemId: id });
    render();
    UI.showToast('Deleted', 'Item has been removed', 'warning');
  }
}
```

### Toggle Completion

```javascript
function toggleItemComplete(id) {
  const item = state.Items.find(i => i.id === id);
  if (!item) return;

  item.completed = !item.completed;

  if (item.completed) {
    Helpers.logActivity('item_completed', `Completed: ${item.name}`, { itemId: id });
    UI.showToast('Done!', `${item.name} completed`, 'success');
  }

  stateManager.update({ Items: state.Items });
  render();
}
```

### Filter/Search Pattern

```javascript
// In screens.js
MyScreen() {
  const filter = getMyFilter();
  const search = getMySearch();

  const filteredItems = state.Items.filter(item => {
    const matchesFilter = filter === 'all' || item.status === filter;
    const matchesSearch = !search ||
      item.name.toLowerCase().includes(search.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  return `
    <select onchange="filterItems(this.value)" aria-label="Filter items">
      <option value="all" ${filter === 'all' ? 'selected' : ''}>All</option>
      <option value="active" ${filter === 'active' ? 'selected' : ''}>Active</option>
    </select>
    <input
      type="text"
      value="${UI.sanitize(search)}"
      onkeyup="searchItems(this.value)"
      placeholder="Search..."
    />
    ${filteredItems.map(item => renderItem(item)).join('')}
  `;
}
```

### Date Formatting

```javascript
// Display date
Helpers.formatDate('2024-01-15');
// "Monday, January 15, 2024"

// Get today
stateManager.getTodayDate();
// "2024-01-15"

// Parse for comparison
new Date(dateStr).getTime();
```

---

## Troubleshooting

### State Not Saving

```javascript
// Check localStorage availability
if (typeof localStorage === 'undefined') {
  console.error('localStorage not available');
}

// Check for quota exceeded
try {
  localStorage.setItem('test', 'test');
  localStorage.removeItem('test');
} catch (e) {
  console.error('localStorage quota exceeded');
}

// Force save
stateManager.saveToStorage();
```

### Screen Not Rendering

```javascript
// Check if screen exists
console.log(Object.keys(ScreenRenderers));

// Check for JS errors in screen function
try {
  const html = ScreenRenderers.MyScreen();
  console.log(html);
} catch (e) {
  console.error('Render error:', e);
}
```

### Modal Not Closing

```javascript
// Check for unclosed tags in modal content
// Check for JS errors in onclick handlers
// Manually close
UI.closeModal();
```

### Data Import Failing

```javascript
// Log the parsed data
console.log(JSON.parse(fileContent));

// Check validation errors
const errors = DataValidator.validateImportData(data);
console.log(errors);
```

### Dark Mode Not Working

```javascript
// Check body classes
console.log(document.body.classList);
console.log(document.documentElement.classList);

// Verify state
console.log(state.Settings.darkMode);

// Manual toggle
document.documentElement.classList.toggle('dark');
```

### Cognitive System Issues

```javascript
// Check initialization
console.log(CognitiveController.initialized);
console.log(CognitiveController.error);
console.log(CognitiveController.payload);

// Retry
await CognitiveController.retry();
```

---

## Performance Tips

1. **Minimize re-renders** - Only call `render()` when necessary
2. **Use debounce** - For search/filter inputs
3. **Batch state updates** - Combine multiple changes into one `update()` call
4. **Limit history size** - `maxHistorySize` prevents memory bloat
5. **Lazy load data** - Only fetch/render what's visible
6. **Use CSS transitions** - Instead of JS animations where possible

---

## Security Considerations

1. **Always sanitize** - Use `UI.sanitize()` for all user input
2. **No eval()** - Never evaluate user-provided strings
3. **Validate imports** - Check structure before applying
4. **No external requests** - Except for cognitive_state.json
5. **localStorage only** - No sensitive data to servers

---

## AI Integration Development

### Adding AI Actions

When adding new actions to `ai-actions.js`:

```javascript
newAction(param1, param2) {
  // 1. Validate inputs
  if (!param1) {
    return { success: false, error: 'param1 is required' };
  }

  // 2. Perform action
  const result = doSomething(param1, param2);

  // 3. Log activity with AI source
  Helpers.logActivity('ai_action_name', 'Description', {
    param1,
    source: 'AI'
  });

  // 4. Update state
  stateManager.update({ ... });

  // 5. Render if UI changed
  render();

  // 6. Show feedback
  UI.showToast('Success', 'Action completed', 'success');

  // 7. Return structured result
  return { success: true, result };
}
```

### Adding Context Data

When adding new data to `AIContext.getContext()`:

```javascript
// In getContext() method
return {
  // ... existing properties ...

  newData: {
    items: state.NewFeature.items,
    summary: {
      total: state.NewFeature.items.length,
      active: state.NewFeature.items.filter(i => i.active).length
    }
  }
};
```

### Testing AI Integration

Run the Node.js test suite:

```bash
node test-ai-integration.js
```

Or test in browser console:

```javascript
// Test context generation
console.log(AIContext.getContext());
console.log(AIContext.getQuickContext());
console.log(AIContext.getClipboardSnapshot());

// Test actions
const result = AIActions.createTask('X', 'Test task', 'Test notes');
console.log(result);

// Test suggestions
console.log(AIActions.suggestDayType());
console.log(AIActions.suggestNextAction());
```

### AI Action Guidelines

1. **Always validate** - Check inputs before processing
2. **Return structured results** - `{ success: boolean, ...data }`
3. **Log with source** - Include `source: 'AI'` in log details
4. **Show UI feedback** - Use `UI.showToast()` for user awareness
5. **Handle errors gracefully** - Return error messages, don't throw
6. **Respect day type** - Consider energy levels in suggestions
7. **Don't overwhelm** - Suggest 1-3 actions at a time
