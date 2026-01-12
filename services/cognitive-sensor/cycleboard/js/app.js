// CycleBoard App Initialization
// Main entry point that initializes all modules

// Initialize state manager (global)
const stateManager = new CycleBoardState();

// State accessor - always returns current stateManager.state
// Use this instead of caching state reference to avoid sync issues
Object.defineProperty(window, 'state', {
  get() { return stateManager.state; },
  set(value) {
    // When setting state, merge into stateManager.state
    Object.keys(stateManager.state).forEach(key => delete stateManager.state[key]);
    Object.assign(stateManager.state, value);
  },
  configurable: true
});

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  // Apply dark mode if saved
  if (state.Settings && state.Settings.darkMode) {
    document.documentElement.classList.add('dark');
  }

  // Initialize main app
  init();

  // Initialize cognitive controller
  CognitiveController.init();
});
