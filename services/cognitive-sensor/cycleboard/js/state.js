// CycleBoard State Management Module
// Handles state persistence, undo/redo, and data migration

// Task Status Constants
const TASK_STATUS = Object.freeze({
  NOT_STARTED: 'Not Started',
  IN_PROGRESS: 'In Progress',
  COMPLETED: 'Completed'
});

// Day Type Constants
const DAY_TYPE = Object.freeze({
  A: 'A',
  B: 'B',
  C: 'C'
});

// Reflection Period Constants
const REFLECTION_PERIOD = Object.freeze({
  WEEKLY: 'weekly',
  MONTHLY: 'monthly',
  QUARTERLY: 'quarterly',
  YEARLY: 'yearly'
});

class CycleBoardState {
  constructor() {
    this.saveDebounceTimer = null;
    this.history = [];
    this.historyIndex = -1;
    this.maxHistorySize = 50;
    this.loadFromStorage();
    if (!this.state || !this.state.AZTask) {
      this.state = this.getDefaultState();
      this.saveToStorage();
    }
    this.initializeDates();
    this.pushHistory(); // Initial state
  }

  getDefaultState() {
    return {
      version: '2.0',
      screen: 'Home',
      AZTask: [
        { id: 'a1', letter: 'A', task: 'Define Monthly Focus', status: 'Not Started', notes: '', createdAt: new Date().toISOString() },
        { id: 'b1', letter: 'B', task: 'Draft A/B/C day templates', status: 'In Progress', notes: '', createdAt: new Date().toISOString() },
      ],
      DayPlans: {},
      FocusArea: [
        { id: 'fa1', name: 'Production', definition: 'Increase output and efficiency', color: '#3B82F6', tasks: [] },
        { id: 'fa2', name: 'Image', definition: 'Build brand and presentation', color: '#10B981', tasks: [] },
        { id: 'fa3', name: 'Growth', definition: 'Learning and skill development', color: '#8B5CF6', tasks: [] },
        { id: 'fa4', name: 'Personal', definition: 'Well-being and relationships', color: '#F59E0B', tasks: [] },
        { id: 'fa5', name: 'Errands', definition: 'Logistics to reduce friction', color: '#EF4444', tasks: [] },
        { id: 'fa6', name: 'Network', definition: 'Expand and nurture connections', color: '#EC4899', tasks: [] }
      ],
      Routine: {
        Morning: ['Hydrate', 'Weather check', 'Oral care', 'Shower', 'Skincare', 'Dress', 'Pack essentials', 'Breakfast', 'Tidy space', 'Walk/Stretch', 'High-priority task'],
        Commute: ['Grab essentials (keys, phone, wallet)', 'Weather check', 'Lock up and leave', 'Enter car/transport', 'Set navigation/playlist', 'Mental prep for day', 'Arrive 15 min early', 'Intentional downtime (10 min)', 'Gather belongings', 'Strategic downtime (5 min)', 'First task setup'],
        Evening: ['Light tidy', 'Prep bag', 'Plan tomorrow', 'Gratitude entry']
      },
      // Day Type Templates - customizable schedules per day type
      DayTypeTemplates: {
        A: {
          name: 'Optimal Day',
          description: 'Full energy, maximum output',
          timeBlocks: [
            { time: '6:00 AM', title: 'Morning Routine', duration: 60 },
            { time: '7:00 AM', title: 'Commute / Prep', duration: 30 },
            { time: '7:30 AM', title: 'Deep Work Block 1', duration: 90 },
            { time: '9:00 AM', title: 'Break / Recharge', duration: 15 },
            { time: '9:15 AM', title: 'Deep Work Block 2', duration: 90 },
            { time: '10:45 AM', title: 'Admin / Email', duration: 30 },
            { time: '11:15 AM', title: 'Deep Work Block 3', duration: 90 },
            { time: '12:45 PM', title: 'Lunch Break', duration: 45 },
            { time: '1:30 PM', title: 'Deep Work Block 4', duration: 90 },
            { time: '3:00 PM', title: 'Meetings / Collaboration', duration: 60 },
            { time: '4:00 PM', title: 'Wrap-up / Planning', duration: 30 },
            { time: '4:30 PM', title: 'Evening Routine', duration: 30 }
          ],
          routines: ['Morning', 'Commute', 'Evening'],
          goals: { baseline: 'Complete 4 deep work blocks', stretch: 'Clear inbox + bonus task' }
        },
        B: {
          name: 'Low Energy Day',
          description: 'Conserve energy, focus on essentials',
          timeBlocks: [
            { time: '7:00 AM', title: 'Light Morning Routine', duration: 45 },
            { time: '7:45 AM', title: 'Easy Start Task', duration: 45 },
            { time: '8:30 AM', title: 'Focus Block 1', duration: 60 },
            { time: '9:30 AM', title: 'Break / Walk', duration: 20 },
            { time: '9:50 AM', title: 'Focus Block 2', duration: 60 },
            { time: '10:50 AM', title: 'Admin / Light Tasks', duration: 40 },
            { time: '11:30 AM', title: 'Early Lunch', duration: 60 },
            { time: '12:30 PM', title: 'Focus Block 3', duration: 60 },
            { time: '1:30 PM', title: 'Rest / Recharge', duration: 30 },
            { time: '2:00 PM', title: 'Light Work / Wrap-up', duration: 60 },
            { time: '3:00 PM', title: 'Evening Routine', duration: 30 }
          ],
          routines: ['Morning', 'Evening'],
          goals: { baseline: 'Complete 3 focus blocks', stretch: 'One bonus task if energy allows' }
        },
        C: {
          name: 'Chaos Day',
          description: 'Survival mode - one priority only',
          timeBlocks: [
            { time: '8:00 AM', title: 'Minimal Morning', duration: 30 },
            { time: '8:30 AM', title: 'Identify ONE Priority', duration: 15 },
            { time: '8:45 AM', title: 'Priority Task', duration: 90 },
            { time: '10:15 AM', title: 'Break / Assess', duration: 15 },
            { time: '10:30 AM', title: 'Continue Priority or Pivot', duration: 60 },
            { time: '11:30 AM', title: 'Lunch / Reset', duration: 60 },
            { time: '12:30 PM', title: 'Damage Control / Urgent Only', duration: 90 },
            { time: '2:00 PM', title: 'Wrap Minimum Viable Day', duration: 30 },
            { time: '2:30 PM', title: 'Rest / Tomorrow Prep', duration: 30 }
          ],
          routines: ['Evening'],
          goals: { baseline: 'Complete ONE priority task', stretch: 'Survive and reset for tomorrow' }
        }
      },
      Settings: {
        darkMode: false,
        notifications: true,
        autoSave: true,
        defaultDayType: 'A'
      },
      History: {
        completedTasks: [],
        productivityScore: 0,
        streak: 0,
        timeline: []
      },
      Journal: [],
      EightSteps: {}, // Track 8 Steps to Success per day - key: date, value: step completions
      Contingencies: {
        runningLate: { enabled: true, actions: ['Skip non-essentials', 'Prioritize first task', 'Communicate with stakeholders'] },
        lowEnergy: { enabled: true, actions: ['Switch to B-Day mode', 'Focus on baseline only', 'Take frequent breaks'] },
        freeTime: { enabled: true, actions: ['Quick wins from list', 'Prep for tomorrow', 'Recharge if needed'] },
        disruption: { enabled: true, actions: ['Reassess priorities', 'Delegate non-urgent', 'Focus on one task'] }
      },
      Reflections: {
        weekly: [],
        monthly: [],
        quarterly: [],
        yearly: []
      },
      MomentumWins: [] // Daily small wins log
    };
  }

  initializeDates() {
    const today = this.getTodayDate();
    if (!this.state.DayPlans[today]) {
      this.state.DayPlans[today] = this.createDefaultDayPlan();
    }
  }

  createDefaultDayPlan() {
    return {
      id: this.generateId(),
      date: this.getTodayDate(),
      day_type: this.state.Settings.defaultDayType,
      time_blocks: [
        { id: this.generateId(), time: '06:00', title: 'Morning Routine', completed: false },
        { id: this.generateId(), time: '08:00', title: 'Deep Work Block', completed: false },
        { id: this.generateId(), time: '12:00', title: 'Break / Walk', completed: false },
        { id: this.generateId(), time: '13:00', title: 'Execution Block', completed: false },
        { id: this.generateId(), time: '18:00', title: 'Evening Routine', completed: false }
      ],
      baseline_goal: { text: 'Ship 1 meaningful outcome', completed: false },
      stretch_goal: { text: 'Ship 2 outcomes + review', completed: false },
      focus_areas: [],
      routines_completed: {},
      notes: '',
      rating: 0,
      progress_snapshots: [],
      final_progress: 0
    };
  }

  getTodayDate() {
    return new Date().toISOString().slice(0, 10);
  }

  generateId() {
    return Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  }

  loadFromStorage() {
    try {
      const saved = localStorage.getItem('cycleboard-state');
      if (saved) {
        this.state = JSON.parse(saved);
        if (!this.state.version) {
          this.migrateFromV1();
        }
        // Ensure History.timeline exists
        if (!this.state.History) {
          this.state.History = this.getDefaultState().History;
        }
        if (!this.state.History.timeline) {
          this.state.History.timeline = [];
        }
        // Ensure Journal exists
        if (!this.state.Journal) {
          this.state.Journal = [];
        }
        // Ensure new state properties exist
        if (!this.state.EightSteps) {
          this.state.EightSteps = {};
        }
        if (!this.state.Contingencies) {
          this.state.Contingencies = this.getDefaultState().Contingencies;
        }
        if (!this.state.Reflections) {
          this.state.Reflections = { weekly: [], monthly: [], quarterly: [], yearly: [] };
        }
        if (!this.state.MomentumWins) {
          this.state.MomentumWins = [];
        }
        // Ensure DayTypeTemplates exist with proper structure
        if (!this.state.DayTypeTemplates ||
            !this.state.DayTypeTemplates.A?.timeBlocks?.length ||
            !this.state.DayTypeTemplates.B?.timeBlocks?.length ||
            !this.state.DayTypeTemplates.C?.timeBlocks?.length) {
          this.state.DayTypeTemplates = this.getDefaultState().DayTypeTemplates;
        }
      }
    } catch (e) {
      console.error('Failed to load state:', e);
      this.state = this.getDefaultState();
    }
  }

  migrateFromV1() {
    if (Array.isArray(this.state.DayPlans)) {
      const dayPlansObj = {};
      this.state.DayPlans.forEach(plan => {
        dayPlansObj[plan.date] = plan;
      });
      this.state.DayPlans = dayPlansObj;
    }
    this.state.version = '2.0';
    this.state.Settings = this.getDefaultState().Settings;
    this.state.History = this.getDefaultState().History;
    if (!this.state.History.timeline) {
      this.state.History.timeline = [];
    }
  }

  saveToStorage() {
    try {
      localStorage.setItem('cycleboard-state', JSON.stringify(this.state));
    } catch (e) {
      console.error('Failed to save state:', e);

      if (e.name === 'QuotaExceededError') {
        // Storage quota exceeded - clean up old data
        this.cleanupOldData();

        // Try again after cleanup
        try {
          localStorage.setItem('cycleboard-state', JSON.stringify(this.state));
          if (typeof UI !== 'undefined') {
            UI.showToast('Storage Warning', 'Cleaned up old data to save space', 'warning');
          }
        } catch (retryError) {
          if (typeof UI !== 'undefined') {
            UI.showToast('Storage Full', 'Please export and clear old data', 'error');
          }
        }
      } else {
        if (typeof UI !== 'undefined') {
          UI.showToast('Save Error', 'Failed to save data locally', 'error');
        }
      }
    }
  }

  cleanupOldData() {
    // Remove old completed tasks (keep last 50)
    if (this.state.History.completedTasks && this.state.History.completedTasks.length > 50) {
      this.state.History.completedTasks = this.state.History.completedTasks
        .sort((a, b) => new Date(b.completedAt) - new Date(a.completedAt))
        .slice(0, 50);
    }

    // Remove old timeline activities (keep last 100)
    if (this.state.History.timeline && this.state.History.timeline.length > 100) {
      this.state.History.timeline = this.state.History.timeline
        .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
        .slice(0, 100);
    }

    // Remove old day plans (keep last 30 days)
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    const cutoffDate = thirtyDaysAgo.toISOString().slice(0, 10);

    Object.keys(this.state.DayPlans).forEach(date => {
      if (date < cutoffDate) {
        delete this.state.DayPlans[date];
      }
    });
  }

  update(updates) {
    Object.assign(this.state, updates);
    this.pushHistory(); // Save state for undo/redo
    if (this.state.Settings.autoSave) {
      this.saveDebounced();
    }
  }

  saveDebounced() {
    clearTimeout(this.saveDebounceTimer);
    this.saveDebounceTimer = setTimeout(() => {
      this.saveToStorage();
    }, 1000); // Save 1 second after last change
  }

  pushHistory() {
    // Remove any states after current index (when undoing and making new changes)
    this.history = this.history.slice(0, this.historyIndex + 1);

    // Add current state as a deep copy
    this.history.push(JSON.parse(JSON.stringify(this.state)));

    // Limit history size
    if (this.history.length > this.maxHistorySize) {
      this.history.shift();
    } else {
      this.historyIndex++;
    }
  }

  undo() {
    if (this.historyIndex > 0) {
      this.historyIndex--;
      this.state = JSON.parse(JSON.stringify(this.history[this.historyIndex]));
      this.saveDebounced();
      return true;
    }
    return false;
  }

  redo() {
    if (this.historyIndex < this.history.length - 1) {
      this.historyIndex++;
      this.state = JSON.parse(JSON.stringify(this.history[this.historyIndex]));
      this.saveDebounced();
      return true;
    }
    return false;
  }

  canUndo() {
    return this.historyIndex > 0;
  }

  canRedo() {
    return this.historyIndex < this.history.length - 1;
  }

  getState() {
    return { ...this.state };
  }
}

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = CycleBoardState;
}
