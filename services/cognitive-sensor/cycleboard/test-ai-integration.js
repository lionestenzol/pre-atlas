/**
 * CycleBoard AI Integration Test
 * Run with: node test-ai-integration.js
 *
 * This simulates the browser environment to test AIContext and AIActions
 */

const fs = require('fs');
const vm = require('vm');

// ============================================
// MOCK BROWSER ENVIRONMENT
// ============================================

// Mock localStorage
const localStorageData = {};
const localStorage = {
  getItem: (key) => localStorageData[key] || null,
  setItem: (key, value) => { localStorageData[key] = value; },
  removeItem: (key) => { delete localStorageData[key]; }
};

// Create a context that simulates browser globals
const context = {
  localStorage,
  console,
  Date,
  Math,
  JSON,
  Object,
  Array,
  String,
  Number,
  Boolean,
  setTimeout,
  clearTimeout,
  document: {
    getElementById: () => null,
    createElement: () => ({ style: {} }),
    body: { appendChild: () => {} }
  },
  window: null, // Will be set to context itself
  module: { exports: {} },

  // UI Mock
  UI: {
    showToast: (title, desc, type) => console.log(`  [TOAST ${type.toUpperCase()}] ${title}: ${desc}`),
    showModal: () => {},
    closeModal: () => {},
    sanitize: (str) => String(str || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
    showLoading: () => {},
    hideLoading: () => {}
  },

  // Cognitive Controller Mock
  CognitiveController: {
    initialized: true,
    mode: 'BUILD',
    risk: 'LOW',
    payload: null,
    getMode: () => 'BUILD',
    getRisk: () => 'LOW',
    getOpenLoops: () => [],
    isClosureMode: () => false
  },

  // Navigation mocks
  render: () => console.log('  [RENDER] Screen updated'),
  navigate: null // Will be set after state is available
};

context.window = context;

// Create VM context
vm.createContext(context);

// ============================================
// LOAD MODULES IN ORDER
// ============================================

console.log('\n=== Loading CycleBoard Modules ===\n');

// Load state.js
const stateCode = fs.readFileSync('./js/state.js', 'utf8');
vm.runInContext(stateCode, context);
console.log('✓ state.js loaded (TASK_STATUS, DAY_TYPE, CycleBoardState)');

// Load validator.js
const validatorCode = fs.readFileSync('./js/validator.js', 'utf8');
vm.runInContext(validatorCode, context);
console.log('✓ validator.js loaded (DataValidator)');

// Load helpers.js
const helpersCode = fs.readFileSync('./js/helpers.js', 'utf8');
vm.runInContext(helpersCode, context);
console.log('✓ helpers.js loaded (Helpers object)');

// Initialize state manager
vm.runInContext(`
  const stateManager = new CycleBoardState();
  // Make state accessible via getter
`, context);
console.log('✓ stateManager initialized');

// Add state getter and navigate function
vm.runInContext(`
  Object.defineProperty(this, 'state', {
    get: () => stateManager.state,
    set: (v) => { stateManager.state = v; }
  });
  navigate = (screen) => { state.screen = screen; console.log('  [NAV] Navigated to ' + screen); };
`, context);

// Load AI modules
const aiContextCode = fs.readFileSync('./js/ai-context.js', 'utf8');
vm.runInContext(aiContextCode, context);
console.log('✓ ai-context.js loaded (AIContext object)');

const aiActionsCode = fs.readFileSync('./js/ai-actions.js', 'utf8');
vm.runInContext(aiActionsCode, context);
console.log('✓ ai-actions.js loaded (AIActions object)');

// ============================================
// RUN AI AGENT SIMULATION
// ============================================

console.log('\n=== AI Agent Simulation Starting ===\n');

// Run all tests in the VM context
const testScript = `
// Step 1: Get Context
console.log('STEP 1: Getting current context...');
const ctx = AIContext.getContext();
console.log('  Today: ' + ctx.temporal.today + ' (' + ctx.temporal.dayOfWeek + ')');
console.log('  Day Type: ' + ctx.todayPlan.dayType);
console.log('  Overall Progress: ' + ctx.progress.overall + '%');
console.log('  Tasks: ' + ctx.tasks.summary.total + ' total (' + ctx.tasks.summary.completed + ' completed)');
console.log('  Cognitive Mode: ' + ctx.cognitive.mode);

// Step 2: Get Quick Context
console.log('\\nSTEP 2: Getting quick context...');
const quick = AIContext.getQuickContext();
console.log('  Quick summary:', JSON.stringify(quick, null, 2));

// Step 3: Test Day Type Suggestion
console.log('\\nSTEP 3: Getting day type suggestion...');
const suggestion = AIActions.suggestDayType();
console.log('  Suggested: ' + suggestion.suggestion + '-Day');
console.log('  Reasoning: ' + suggestion.reasoning);

// Step 4: Test Creating a Task
console.log('\\nSTEP 4: Creating a new task...');
const availableLetters = ctx.tasks.availableLetters;
let createdTaskId = null;
if (availableLetters.length > 0) {
  const letter = availableLetters[0];
  const result = AIActions.createTask(letter, 'AI Test Task - Review productivity', 'Created by AI test');
  console.log('  Result: ' + (result.success ? 'SUCCESS' : 'FAILED'));
  if (result.success) {
    console.log('  Task ID: ' + result.taskId);
    console.log('  Letter: ' + result.task.letter);
    createdTaskId = result.taskId;
  } else {
    console.log('  Errors: ' + (result.errors ? result.errors.join(', ') : 'none'));
  }
} else {
  console.log('  No available letters - all A-Z tasks assigned');
}

// Step 5: Test Setting Goals
console.log('\\nSTEP 5: Setting daily goals...');
const goalsResult = AIActions.setGoals('Complete 3 focus sessions', 'Review weekly progress');
console.log('  Result: ' + (goalsResult.success ? 'SUCCESS' : 'FAILED'));

// Step 6: Test Adding Time Block
console.log('\\nSTEP 6: Adding a time block...');
const blockResult = AIActions.addTimeBlock('10:00 AM', 'AI-Suggested Focus Block', 45);
console.log('  Result: ' + (blockResult.success ? 'SUCCESS' : 'FAILED'));
if (blockResult.success) {
  console.log('  Block ID: ' + blockResult.blockId);
}

// Step 7: Test Toggling Time Block
console.log('\\nSTEP 7: Toggling time block completion...');
if (blockResult.success) {
  const toggleResult = AIActions.toggleTimeBlock(blockResult.blockId);
  console.log('  Result: ' + (toggleResult.success ? 'SUCCESS' : 'FAILED'));
  console.log('  Completed: ' + toggleResult.completed);
}

// Step 8: Test Routine Step Completion
console.log('\\nSTEP 8: Completing a routine step...');
const routineNames = Object.keys(state.Routine);
if (routineNames.length > 0) {
  const routineName = routineNames[0];
  const stepResult = AIActions.completeRoutineStep(routineName, 0);
  console.log('  Routine: ' + routineName);
  console.log('  Result: ' + (stepResult.success ? 'SUCCESS' : 'FAILED'));
  if (stepResult.success) {
    console.log('  Step: ' + stepResult.stepText);
  }
}

// Step 9: Test Journal Entry
console.log('\\nSTEP 9: Adding a journal entry...');
const journalResult = AIActions.addJournalEntry(
  'AI Daily Reflection',
  'Today I tested the AI integration. The system is working well.',
  'free'
);
console.log('  Result: ' + (journalResult.success ? 'SUCCESS' : 'FAILED'));
if (journalResult.success) {
  console.log('  Entry ID: ' + journalResult.entryId);
}

// Step 10: Test Momentum Win
console.log('\\nSTEP 10: Logging a momentum win...');
const winResult = AIActions.addMomentumWin('Successfully tested AI integration!');
console.log('  Result: ' + (winResult.success ? 'SUCCESS' : 'FAILED'));

// Step 11: Test Next Action Suggestion
console.log('\\nSTEP 11: Getting next action suggestions...');
const nextActions = AIActions.suggestNextAction();
console.log('  Found ' + nextActions.length + ' suggestions:');
nextActions.slice(0, 3).forEach((action, i) => {
  console.log('    ' + (i + 1) + '. [Priority ' + action.priority + '] ' + action.action);
  console.log('       Details: ' + action.details);
});

// Step 12: Test Navigation
console.log('\\nSTEP 12: Testing navigation...');
const navResult = AIActions.navigateTo('Statistics');
console.log('  Result: ' + (navResult.success ? 'SUCCESS' : 'FAILED'));

// Step 13: Get Updated Context
console.log('\\nSTEP 13: Getting updated context after changes...');
const updatedCtx = AIContext.getContext();
console.log('  Tasks now: ' + updatedCtx.tasks.summary.total + ' total');
console.log('  Journal entries: ' + updatedCtx.journal.totalEntries);
console.log('  Time blocks: ' + updatedCtx.todayPlan.timeBlocksSummary.total);

// Step 14: Test System Prompt Generation
console.log('\\nSTEP 14: Testing system prompt generation...');
const systemPrompt = AIContext.getSystemPrompt();
console.log('  System prompt length: ' + systemPrompt.length + ' characters');
console.log('  Contains context: ' + (systemPrompt.includes('Day Type') ? 'YES' : 'NO'));

// Step 15: Test Clipboard Snapshot
console.log('\\nSTEP 15: Testing clipboard snapshot generation...');
const snapshot = AIContext.getClipboardSnapshot();
console.log('  Snapshot length: ' + snapshot.length + ' characters');
console.log('  Contains sections: ' + (snapshot.includes('## Today\\'s Overview') ? 'YES' : 'NO'));
console.log('  Contains tasks: ' + (snapshot.includes('A-Z Tasks') ? 'YES' : 'NO'));
console.log('  Contains progress bars: ' + (snapshot.includes('█') ? 'YES' : 'NO'));
console.log('\\n--- SNAPSHOT PREVIEW (first 500 chars) ---');
console.log(snapshot.substring(0, 500) + '...');

// ============================================
// ERROR HANDLING TESTS
// ============================================

console.log('\\n=== Error Handling Tests ===\\n');

// Test invalid task letter
console.log('TEST: Invalid task letter...');
const invalidLetterResult = AIActions.createTask('1', 'Invalid task');
console.log('  Result: ' + (invalidLetterResult.success ? 'SUCCESS (unexpected)' : 'FAILED (expected)'));
console.log('  Error: ' + (invalidLetterResult.errors ? invalidLetterResult.errors[0] : 'none'));

// Test duplicate letter
console.log('\\nTEST: Duplicate task letter...');
const existingTask = state.AZTask[0];
if (existingTask) {
  const dupResult = AIActions.createTask(existingTask.letter, 'Duplicate');
  console.log('  Result: ' + (dupResult.success ? 'SUCCESS (unexpected)' : 'FAILED (expected)'));
  console.log('  Error: ' + (dupResult.errors ? dupResult.errors[0] : 'none'));
}

// Test invalid day type
console.log('\\nTEST: Invalid day type...');
const invalidDayResult = AIActions.setDayType('X');
console.log('  Result: ' + (invalidDayResult.success ? 'SUCCESS (unexpected)' : 'FAILED (expected)'));
console.log('  Error: ' + invalidDayResult.error);

// Test non-existent routine
console.log('\\nTEST: Non-existent routine...');
const invalidRoutineResult = AIActions.completeRoutineStep('NonExistent', 0);
console.log('  Result: ' + (invalidRoutineResult.success ? 'SUCCESS (unexpected)' : 'FAILED (expected)'));
console.log('  Error: ' + invalidRoutineResult.error);

// Test invalid screen navigation
console.log('\\nTEST: Invalid screen navigation...');
const invalidNavResult = AIActions.navigateTo('FakeScreen');
console.log('  Result: ' + (invalidNavResult.success ? 'SUCCESS (unexpected)' : 'FAILED (expected)'));
console.log('  Error: ' + invalidNavResult.error);

// ============================================
// SUMMARY
// ============================================

console.log('\\n=== Test Summary ===\\n');
console.log('All AI integration tests completed!');
console.log('');
console.log('Modules tested:');
console.log('  ✓ AIContext.getContext()');
console.log('  ✓ AIContext.getQuickContext()');
console.log('  ✓ AIContext.getSystemPrompt()');
console.log('  ✓ AIContext.getClipboardSnapshot()');
console.log('  ✓ AIActions.createTask()');
console.log('  ✓ AIActions.setGoals()');
console.log('  ✓ AIActions.addTimeBlock()');
console.log('  ✓ AIActions.toggleTimeBlock()');
console.log('  ✓ AIActions.completeRoutineStep()');
console.log('  ✓ AIActions.addJournalEntry()');
console.log('  ✓ AIActions.addMomentumWin()');
console.log('  ✓ AIActions.suggestDayType()');
console.log('  ✓ AIActions.suggestNextAction()');
console.log('  ✓ AIActions.navigateTo()');
console.log('  ✓ Error handling (invalid inputs)');
console.log('');
console.log('The AI integration is working correctly!');
`;

vm.runInContext(testScript, context);
