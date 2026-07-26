// CycleBoard Helpers Module
// Utility functions for calculations, formatting, and data retrieval

const Helpers = {
  formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric'
    });
  },

  calculateCompletionPercentage() {
    const total = state.AZTask.length;
    const done = state.AZTask.filter(t => t.status === 'Completed').length;
    return total ? Math.round((done / total) * 100) : 0;
  },

  getDayPlan(date = null) {
    const targetDate = date || stateManager.getTodayDate();
    if (!state.DayPlans[targetDate]) {
      state.DayPlans[targetDate] = stateManager.createDefaultDayPlan();
      stateManager.update({ DayPlans: state.DayPlans });
    }
    return state.DayPlans[targetDate];
  },

  getWeeklyStats() {
    const today = new Date();
    const weekStart = new Date(today);
    weekStart.setDate(today.getDate() - today.getDay());

    let completed = 0;
    let total = 0;

    for (let i = 0; i < 7; i++) {
      const date = new Date(weekStart);
      date.setDate(weekStart.getDate() + i);
      const dateStr = date.toISOString().slice(0, 10);

      if (state.DayPlans[dateStr]) {
        const plan = state.DayPlans[dateStr];
        if (plan.baseline_goal.completed) completed++;
        total++;
      }
    }

    return { completed, total, percentage: total ? Math.round((completed / total) * 100) : 0 };
  },

  logActivity(type, description, details = {}) {
    if (!state.History.timeline) state.History.timeline = [];

    const activity = {
      id: stateManager.generateId(),
      type: type,
      description: description,
      details: details,
      timestamp: new Date().toISOString()
    };

    state.History.timeline.push(activity);
    stateManager.update({ History: state.History });
  },

  calculateDailyProgress(date = null) {
    const targetDate = date || stateManager.getTodayDate();
    const dayPlan = state.DayPlans[targetDate];

    if (!dayPlan) {
      return {
        overall: 0,
        timeBlocks: { completed: 0, total: 0, percentage: 0 },
        goals: { completed: 0, total: 0, percentage: 0 },
        routines: { completed: 0, total: 0, percentage: 0 },
        focusAreas: { completed: 0, total: 0, percentage: 0 },
        breakdown: []
      };
    }

    // Time Blocks Progress
    const timeBlocksTotal = dayPlan.time_blocks.length;
    const timeBlocksCompleted = dayPlan.time_blocks.filter(b => b.completed).length;
    const timeBlocksPct = timeBlocksTotal ? Math.round((timeBlocksCompleted / timeBlocksTotal) * 100) : 0;

    // Goals Progress
    let goalsCompleted = 0;
    let goalsTotal = 0;
    if (dayPlan.baseline_goal && dayPlan.baseline_goal.text) {
      goalsTotal++;
      if (dayPlan.baseline_goal.completed) goalsCompleted++;
    }
    if (dayPlan.stretch_goal && dayPlan.stretch_goal.text) {
      goalsTotal++;
      if (dayPlan.stretch_goal.completed) goalsCompleted++;
    }
    const goalsPct = goalsTotal ? Math.round((goalsCompleted / goalsTotal) * 100) : 0;

    // Routines Progress
    const routineTypes = Object.keys(state.Routine);
    let routinesCompleted = 0;
    let routinesTotal = routineTypes.length;

    if (dayPlan.routines_completed) {
      routineTypes.forEach(routineName => {
        if (dayPlan.routines_completed[routineName] && dayPlan.routines_completed[routineName].completed) {
          routinesCompleted++;
        }
      });
    }
    const routinesPct = routinesTotal ? Math.round((routinesCompleted / routinesTotal) * 100) : 0;

    // Focus Areas Progress
    let focusTasksCompleted = 0;
    let focusTasksTotal = 0;
    state.FocusArea.forEach(area => {
      if (area.tasks && area.tasks.length > 0) {
        focusTasksTotal += area.tasks.length;
        focusTasksCompleted += area.tasks.filter(t => t.completed).length;
      }
    });
    const focusPct = focusTasksTotal ? Math.round((focusTasksCompleted / focusTasksTotal) * 100) : 0;

    // Calculate Overall Progress (weighted average)
    // Weight: Time blocks 30%, Goals 30%, Routines 25%, Focus 15%
    let overall = 0;
    let totalWeight = 0;

    if (timeBlocksTotal > 0) {
      overall += timeBlocksPct * 0.30;
      totalWeight += 0.30;
    }
    if (goalsTotal > 0) {
      overall += goalsPct * 0.30;
      totalWeight += 0.30;
    }
    if (routinesTotal > 0) {
      overall += routinesPct * 0.25;
      totalWeight += 0.25;
    }
    if (focusTasksTotal > 0) {
      overall += focusPct * 0.15;
      totalWeight += 0.15;
    }

    overall = totalWeight > 0 ? Math.round(overall / totalWeight) : 0;

    return {
      overall,
      timeBlocks: { completed: timeBlocksCompleted, total: timeBlocksTotal, percentage: timeBlocksPct },
      goals: { completed: goalsCompleted, total: goalsTotal, percentage: goalsPct },
      routines: { completed: routinesCompleted, total: routinesTotal, percentage: routinesPct },
      focusAreas: { completed: focusTasksCompleted, total: focusTasksTotal, percentage: focusPct },
      breakdown: [
        { label: 'Time Blocks', completed: timeBlocksCompleted, total: timeBlocksTotal, percentage: timeBlocksPct, icon: 'fa-clock', color: 'blue' },
        { label: 'Goals', completed: goalsCompleted, total: goalsTotal, percentage: goalsPct, icon: 'fa-bullseye', color: 'green' },
        { label: 'Routines', completed: routinesCompleted, total: routinesTotal, percentage: routinesPct, icon: 'fa-list-check', color: 'purple' },
        { label: 'Focus Areas', completed: focusTasksCompleted, total: focusTasksTotal, percentage: focusPct, icon: 'fa-star', color: 'orange' }
      ]
    };
  },

  saveProgressSnapshot(date = null) {
    const targetDate = date || stateManager.getTodayDate();
    const dayPlan = state.DayPlans[targetDate];
    if (!dayPlan) return;

    if (!dayPlan.progress_snapshots) dayPlan.progress_snapshots = [];

    const progress = this.calculateDailyProgress(targetDate);
    const snapshot = {
      timestamp: new Date().toISOString(),
      overall: progress.overall,
      breakdown: progress.breakdown
    };

    dayPlan.progress_snapshots.push(snapshot);
    dayPlan.final_progress = progress.overall;

    stateManager.update({ DayPlans: state.DayPlans });

    // Check for milestones
    this.checkProgressMilestones(progress.overall);
  },

  checkProgressMilestones(progressPct) {
    const milestones = [
      { threshold: 25, message: 'Great start! 25% complete', icon: '🌱' },
      { threshold: 50, message: 'Halfway there! Keep going', icon: '⚡' },
      { threshold: 75, message: 'Almost done! 75% complete', icon: '🔥' },
      { threshold: 100, message: 'Perfect day! 100% complete', icon: '🎉' }
    ];

    const todayDate = stateManager.getTodayDate();
    const completedMilestones = JSON.parse(localStorage.getItem(`milestones-${todayDate}`) || '[]');

    milestones.forEach(milestone => {
      if (progressPct >= milestone.threshold && !completedMilestones.includes(milestone.threshold)) {
        UI.showToast('Milestone Reached!', `${milestone.icon} ${milestone.message}`, 'success');
        completedMilestones.push(milestone.threshold);
        localStorage.setItem(`milestones-${todayDate}`, JSON.stringify(completedMilestones));
      }
    });
  },

  getProgressStreak() {
    const today = new Date();
    let streak = 0;
    let currentDate = new Date(today);

    // Check backwards from today
    while (true) {
      const dateStr = currentDate.toISOString().slice(0, 10);
      const dayPlan = state.DayPlans[dateStr];

      // Consider a day "successful" if progress >= 70%
      if (dayPlan && dayPlan.final_progress >= 70) {
        streak++;
        currentDate.setDate(currentDate.getDate() - 1);
      } else if (dateStr === stateManager.getTodayDate()) {
        // Today doesn't break the streak yet
        currentDate.setDate(currentDate.getDate() - 1);
      } else {
        break;
      }

      // Safety limit
      if (streak > 365) break;
    }

    return streak;
  },

  getProgressHistory(days = 7) {
    const history = [];
    const today = new Date();

    for (let i = days - 1; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(today.getDate() - i);
      const dateStr = date.toISOString().slice(0, 10);
      const dayPlan = state.DayPlans[dateStr];

      history.push({
        date: dateStr,
        dateFormatted: this.formatDate(dateStr),
        progress: dayPlan ? (dayPlan.final_progress || 0) : 0,
        hasData: !!dayPlan
      });
    }

    return history;
  },

  getAverageProgress(days = 7) {
    const history = this.getProgressHistory(days);
    const validDays = history.filter(day => day.hasData);

    if (validDays.length === 0) return 0;

    const sum = validDays.reduce((acc, day) => acc + day.progress, 0);
    return Math.round(sum / validDays.length);
  },

  // ---------------------------------------------------------------------------
  // Minimal Mode — Daily execution lens
  // ---------------------------------------------------------------------------

  // block.time is stored in two formats: seeded blocks use "6:00 AM", blocks
  // edited through input[type=time] use "13:00". convertTo24Hour normalizes both.
  _blockMinutes(block) {
    const [h, m] = convertTo24Hour(block.time).split(':');
    return parseInt(h, 10) * 60 + parseInt(m, 10);
  },

  _sortedBlocks(plan) {
    if (!plan || !plan.time_blocks) return [];
    return [...plan.time_blocks].sort((a, b) => this._blockMinutes(a) - this._blockMinutes(b));
  },

  _nowMinutes() {
    const now = new Date();
    return now.getHours() * 60 + now.getMinutes();
  },

  // The block you're inside right now: the last one whose start time has passed.
  // Returns null before the day's first block starts.
  getCurrentTimeBlock(plan) {
    const nowMin = this._nowMinutes();
    let current = null;
    for (const block of this._sortedBlocks(plan)) {
      if (this._blockMinutes(block) > nowMin) break;
      current = block;
    }
    return current;
  },

  getNextTimeBlock(plan) {
    const nowMin = this._nowMinutes();
    return this._sortedBlocks(plan).find(block => this._blockMinutes(block) > nowMin) || null;
  },

  // Routine attached to the current block, with step progress. Null if the
  // current block's title doesn't name a routine.
  getActiveRoutine(plan) {
    const block = this.getCurrentTimeBlock(plan);
    if (!block) return null;

    const name = _findRoutineMatch(block.title);
    if (!name) return null;

    const steps = this.computeRoutineStepTimes(block.time, state.Routine[name] || []);
    const completion = plan.routines_completed?.[name] || { completed: false, steps: {} };
    const done = steps.filter((_, idx) => completion.steps?.[idx]).length;

    return { name, steps, completion, done, total: steps.length };
  },

  // Stamps each routine step with a real clock time by walking forward from
  // the parent block's start, accumulating each step's duration in turn.
  // Re-scheduling the block automatically re-times every step under it.
  computeRoutineStepTimes(blockTime, steps) {
    let minutes = this._blockMinutes({ time: blockTime });
    return steps.map(step => {
      const duration = step.duration || 5;
      const h = Math.floor(minutes / 60) % 24;
      const m = minutes % 60;
      const time = convertTo12Hour(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`);
      minutes += duration;
      return { ...step, time, duration };
    });
  },

  isPlanReady(plan) {
    return !!(plan && plan.time_blocks && plan.time_blocks.length > 0);
  }
};

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = Helpers;
}
