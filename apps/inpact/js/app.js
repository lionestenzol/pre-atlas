// inPACT App Initialization
// Main entry point

// Initialize state manager (global)
const stateManager = new CycleBoardState();

// State accessor - always returns current stateManager.state
Object.defineProperty(window, 'state', {
  get() { return stateManager.state; },
  set(value) {
    Object.keys(stateManager.state).forEach(key => delete stateManager.state[key]);
    Object.assign(stateManager.state, value);
  },
  configurable: true
});

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  // Apply dark mode from settings
  if (state.Settings.darkMode) {
    document.documentElement.classList.add('dark');
    document.body.classList.add('bg-gray-900', 'text-white');
  }

  // Initialize main app
  init();
});
