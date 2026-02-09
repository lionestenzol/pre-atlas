// CycleBoard AI Actions Module
// Provides a structured interface for AI agents to interact with CycleBoard

const AIActions = {
  // ============================================
  // TASK MANAGEMENT
  // ============================================

  /**
   * Create a new A-Z task
   * @param {string} letter - Single uppercase letter A-Z
   * @param {string} taskText - Task description
   * @param {string} notes - Optional notes
   * @returns {Object} Result with success status and taskId or errors
   */
  createTask(letter, taskText, notes = '') {
    // Validate letter
    letter = letter.toUpperCase();
    if (!/^[A-Z]$/.test(letter)) {
      return { success: false, errors: ['Letter must be a single uppercase letter A-Z'] };
    }

    // Check if letter already used
    const existingTask = state.AZTask.find(t => t.letter === letter);
    if (existingTask) {
      return { success: false, errors: [`Letter ${letter} is already assigned to task: ${existingTask.task}`] };
    }

    const task = {
      id: stateManager.generateId(),
      letter: letter,
      task: taskText.trim(),
      notes: notes.trim(),
      status: TASK_STATUS.NOT_STARTED,
      createdAt: new Date().toISOString()
    };

    // Validate
    const errors = DataValidator.validateTask(task);
    if (errors.length) {
      return { success: false, errors };
    }

    state.AZTask.push(task);
    stateManager.update({ AZTask: state.AZTask });
    Helpers.logActivity('ai_task_created', `AI created task: ${letter} - ${taskText}`, { taskId: task.id, source: 'AI' });
    render();
    UI.showToast('Task Created', `${letter} - ${taskText}`, 'success');

    return { success: true, taskId: task.id, task };
  },

  /**
   * Complete a task by ID
   * @param {string} taskId - Task ID
   * @returns {Object} Result with success status
   */
  completeTask(taskId) {
    const task = state.AZTask.find(t => t.id === taskId);
    if (!task) {
      return { success: false, error: 'Task not found' };
    }

    if (task.status === TASK_STATUS.COMPLETED) {
      return { success: false, error: 'Task is already completed' };
    }

    task.status = TASK_STATUS.COMPLETED;
    state.History.completedTasks.push({
      taskId: task.id,
      completedAt: new Date().toISOString()
    });

    Helpers.logActivity('ai_task_completed', `AI completed task: ${task.letter} - ${task.task}`, { taskId: task.id, source: 'AI' });
    stateManager.update({ AZTask: state.AZTask, History: state.History });
    render();
    UI.showToast('Task Completed', `${task.letter} - ${task.task}`, 'success');

    return { success: true, task };
  },

  /**
   * Update a task's status
   * @param {string} taskId - Task ID
   * @param {string} status - New status (use TASK_STATUS constants)
   * @returns {Object} Result with success status
   */
  updateTaskStatus(taskId, status) {
    const task = state.AZTask.find(t => t.id === taskId);
    if (!task) {
      return { success: false, error: 'Task not found' };
    }

    if (!Object.values(TASK_STATUS).includes(status)) {
      return { success: false, error: `Invalid status. Use: ${Object.values(TASK_STATUS).join(', ')}` };
    }

    const oldStatus = task.status;
    task.status = status;

    if (status === TASK_STATUS.COMPLETED && oldStatus !== TASK_STATUS.COMPLETED) {
      state.History.completedTasks.push({
        taskId: task.id,
        completedAt: new Date().toISOString()
      });
    }

    Helpers.logActivity('ai_task_status_changed', `AI changed task ${task.letter} status: ${oldStatus} -> ${status}`, { taskId, oldStatus, newStatus: status, source: 'AI' });
    stateManager.update({ AZTask: state.AZTask, History: state.History });
    render();

    return { success: true, task };
  },

  /**
   * Update a task's text or notes
   * @param {string} taskId - Task ID
   * @param {Object} updates - { task?: string, notes?: string }
   * @returns {Object} Result with success status
   */
  updateTask(taskId, updates) {
    const task = state.AZTask.find(t => t.id === taskId);
    if (!task) {
      return { success: false, error: 'Task not found' };
    }

    if (updates.task !== undefined) {
      task.task = updates.task.trim();
    }
    if (updates.notes !== undefined) {
      task.notes = updates.notes.trim();
    }

    const errors = DataValidator.validateTask(task);
    if (errors.length) {
      return { success: false, errors };
    }

    Helpers.logActivity('ai_task_updated', `AI updated task: ${task.letter}`, { taskId, updates, source: 'AI' });
    stateManager.update({ AZTask: state.AZTask });
    render();

    return { success: true, task };
  },

  /**
   * Find task by letter
   * @param {string} letter - Letter A-Z
   * @returns {Object|null} Task object or null
   */
  findTaskByLetter(letter) {
    return state.AZTask.find(t => t.letter === letter.toUpperCase()) || null;
  },

  // ============================================
  // DAY PLANNING
  // ============================================

  /**
   * Set the day type for today
   * @param {string} type - 'A', 'B', or 'C'
   * @param {boolean} applyTemplate - Whether to apply the day template
   * @returns {Object} Result with success status
   */
  setDayType(type, applyTemplate = false) {
    type = type.toUpperCase();
    if (!['A', 'B', 'C'].includes(type)) {
      return { success: false, error: 'Invalid day type. Use A, B, or C' };
    }

    const plan = Helpers.getDayPlan();
    const oldType = plan.day_type;
    plan.day_type = type;

    if (applyTemplate) {
      const template = state.DayTypeTemplates?.[type];
      if (template) {
        plan.time_blocks = template.timeBlocks.map(block => ({
          id: stateManager.generateId(),
          time: block.time,
          title: block.title,
          duration: block.duration,
          completed: false
        }));
        plan.baseline_goal = { text: template.goals.baseline, completed: false };
        plan.stretch_goal = { text: template.goals.stretch, completed: false };
        plan.activeRoutines = template.routines;
      }
    }

    Helpers.logActivity('ai_day_type_set', `AI set day type to ${type}${applyTemplate ? ' with template' : ''}`, { from: oldType, to: type, templateApplied: applyTemplate, source: 'AI' });
    state.DayPlans[stateManager.getTodayDate()] = plan;
    stateManager.update({ DayPlans: state.DayPlans });
    render();
    UI.showToast('Day Type Set', `Changed to ${type}-Day`, 'success');

    return { success: true, dayType: type, plan };
  },

  /**
   * Set baseline and/or stretch goals for today
   * @param {string} baseline - Baseline goal text (optional)
   * @param {string} stretch - Stretch goal text (optional)
   * @returns {Object} Result with success status
   */
  setGoals(baseline = null, stretch = null) {
    const plan = Helpers.getDayPlan();

    if (baseline !== null) {
      plan.baseline_goal = { text: baseline.trim(), completed: false };
    }
    if (stretch !== null) {
      plan.stretch_goal = { text: stretch.trim(), completed: false };
    }

    Helpers.logActivity('ai_goals_set', 'AI set daily goals', { baseline, stretch, source: 'AI' });
    state.DayPlans[stateManager.getTodayDate()] = plan;
    stateManager.update({ DayPlans: state.DayPlans });
    render();
    UI.showToast('Goals Updated', 'Daily goals have been set', 'success');

    return { success: true, plan };
  },

  /**
   * Toggle goal completion
   * @param {string} goalType - 'baseline' or 'stretch'
   * @returns {Object} Result with success status
   */
  toggleGoal(goalType) {
    if (!['baseline', 'stretch'].includes(goalType)) {
      return { success: false, error: 'goalType must be "baseline" or "stretch"' };
    }

    const plan = Helpers.getDayPlan();
    const goalKey = goalType === 'baseline' ? 'baseline_goal' : 'stretch_goal';

    plan[goalKey].completed = !plan[goalKey].completed;

    Helpers.logActivity('ai_goal_toggled', `AI ${plan[goalKey].completed ? 'completed' : 'uncompleted'} ${goalType} goal`, { goalType, completed: plan[goalKey].completed, source: 'AI' });
    state.DayPlans[stateManager.getTodayDate()] = plan;
    stateManager.update({ DayPlans: state.DayPlans });
    render();

    return { success: true, completed: plan[goalKey].completed };
  },

  // ============================================
  // TIME BLOCKS
  // ============================================

  /**
   * Add a time block to today's plan
   * @param {string} time - Time string (e.g., "9:00 AM" or "14:00")
   * @param {string} title - Block title
   * @param {number} duration - Duration in minutes (optional)
   * @returns {Object} Result with success status and blockId
   */
  addTimeBlock(time, title, duration = 60) {
    const plan = Helpers.getDayPlan();

    const block = {
      id: stateManager.generateId(),
      time: time,
      title: title.trim(),
      duration: duration,
      completed: false
    };

    plan.time_blocks.push(block);

    // Sort by time
    plan.time_blocks.sort((a, b) => {
      const timeA = this._parseTime(a.time);
      const timeB = this._parseTime(b.time);
      return timeA - timeB;
    });

    Helpers.logActivity('ai_time_block_added', `AI added time block: ${time} - ${title}`, { blockId: block.id, source: 'AI' });
    state.DayPlans[stateManager.getTodayDate()] = plan;
    stateManager.update({ DayPlans: state.DayPlans });
    render();
    UI.showToast('Time Block Added', `${time} - ${title}`, 'success');

    return { success: true, blockId: block.id, block };
  },

  /**
   * Toggle a time block's completion status
   * @param {string} blockId - Time block ID
   * @returns {Object} Result with success status
   */
  toggleTimeBlock(blockId) {
    const plan = Helpers.getDayPlan();
    const block = plan.time_blocks.find(b => b.id === blockId);

    if (!block) {
      return { success: false, error: 'Time block not found' };
    }

    block.completed = !block.completed;

    Helpers.logActivity('ai_time_block_toggled', `AI ${block.completed ? 'completed' : 'uncompleted'} time block: ${block.title}`, { blockId, completed: block.completed, source: 'AI' });
    state.DayPlans[stateManager.getTodayDate()] = plan;
    stateManager.update({ DayPlans: state.DayPlans });
    render();

    return { success: true, completed: block.completed, block };
  },

  /**
   * Delete a time block
   * @param {string} blockId - Time block ID
   * @returns {Object} Result with success status
   */
  deleteTimeBlock(blockId) {
    const plan = Helpers.getDayPlan();
    const blockIndex = plan.time_blocks.findIndex(b => b.id === blockId);

    if (blockIndex === -1) {
      return { success: false, error: 'Time block not found' };
    }

    const block = plan.time_blocks[blockIndex];
    plan.time_blocks.splice(blockIndex, 1);

    Helpers.logActivity('ai_time_block_deleted', `AI deleted time block: ${block.title}`, { blockId, source: 'AI' });
    state.DayPlans[stateManager.getTodayDate()] = plan;
    stateManager.update({ DayPlans: state.DayPlans });
    render();

    return { success: true };
  },

  // ============================================
  // ROUTINES
  // ============================================

  /**
   * Complete a specific routine step
   * @param {string} routineName - Name of the routine (e.g., "Morning")
   * @param {number} stepIndex - Index of the step (0-based)
   * @returns {Object} Result with success status
   */
  completeRoutineStep(routineName, stepIndex) {
    if (!state.Routine[routineName]) {
      return { success: false, error: `Routine "${routineName}" not found. Available: ${Object.keys(state.Routine).join(', ')}` };
    }

    const steps = state.Routine[routineName];
    if (stepIndex < 0 || stepIndex >= steps.length) {
      return { success: false, error: `Step index ${stepIndex} out of range. Routine has ${steps.length} steps (0-${steps.length - 1})` };
    }

    const plan = Helpers.getDayPlan();
    if (!plan.routines_completed[routineName]) {
      plan.routines_completed[routineName] = { completed: false, steps: {} };
    }

    plan.routines_completed[routineName].steps[stepIndex] = true;

    // Check if all steps are completed
    const allCompleted = steps.every((_, idx) => plan.routines_completed[routineName].steps[idx]);
    if (allCompleted) {
      plan.routines_completed[routineName].completed = true;
    }

    Helpers.logActivity('ai_routine_step_completed', `AI completed ${routineName} step: ${steps[stepIndex]}`, { routineName, stepIndex, stepText: steps[stepIndex], source: 'AI' });
    state.DayPlans[stateManager.getTodayDate()] = plan;
    stateManager.update({ DayPlans: state.DayPlans });
    render();

    return { success: true, stepText: steps[stepIndex], routineComplete: allCompleted };
  },

  /**
   * Mark entire routine as complete
   * @param {string} routineName - Name of the routine
   * @returns {Object} Result with success status
   */
  completeRoutine(routineName) {
    if (!state.Routine[routineName]) {
      return { success: false, error: `Routine "${routineName}" not found` };
    }

    const plan = Helpers.getDayPlan();
    const steps = state.Routine[routineName];

    plan.routines_completed[routineName] = {
      completed: true,
      steps: Object.fromEntries(steps.map((_, idx) => [idx, true]))
    };

    Helpers.logActivity('ai_routine_completed', `AI completed entire ${routineName} routine`, { routineName, source: 'AI' });
    state.DayPlans[stateManager.getTodayDate()] = plan;
    stateManager.update({ DayPlans: state.DayPlans });
    render();
    UI.showToast('Routine Complete', `${routineName} routine finished!`, 'success');

    return { success: true };
  },

  // ============================================
  // JOURNAL
  // ============================================

  /**
   * Add a journal entry
   * @param {string} title - Entry title
   * @param {string} content - Entry content
   * @param {string} entryType - 'free', 'weekly', or 'gratitude'
   * @param {string} mood - Optional mood emoji
   * @returns {Object} Result with success status and entryId
   */
  addJournalEntry(title, content, entryType = 'free', mood = null) {
    const validTypes = ['free', 'weekly', 'gratitude'];
    if (!validTypes.includes(entryType)) {
      return { success: false, error: `Invalid entry type. Use: ${validTypes.join(', ')}` };
    }

    // Validate inputs inline (DataValidator doesn't have validateJournalEntry)
    const errors = [];
    if (!title || title.trim().length === 0) {
      errors.push('Title is required');
    }
    if (title && title.length > 200) {
      errors.push('Title too long (max 200 characters)');
    }
    if (!content || content.trim().length === 0) {
      errors.push('Content is required');
    }
    if (content && content.length > 5000) {
      errors.push('Content too long (max 5000 characters)');
    }
    if (errors.length) {
      return { success: false, errors };
    }

    const entry = {
      id: stateManager.generateId(),
      title: title.trim(),
      content: content.trim(),
      entryType: entryType,
      tags: [],
      mood: mood,
      timestamp: new Date().toISOString()
    };

    state.Journal.push(entry);
    Helpers.logActivity('ai_journal_created', `AI created journal entry: ${title}`, { entryId: entry.id, entryType, source: 'AI' });
    stateManager.update({ Journal: state.Journal });
    render();
    UI.showToast('Journal Entry Added', title, 'success');

    return { success: true, entryId: entry.id, entry };
  },

  // ============================================
  // MOMENTUM WINS
  // ============================================

  /**
   * Add a momentum win (small daily win)
   * @param {string} description - Win description
   * @returns {Object} Result with success status
   */
  addMomentumWin(description) {
    const win = {
      id: stateManager.generateId(),
      description: description.trim(),
      date: stateManager.getTodayDate(),
      timestamp: new Date().toISOString()
    };

    if (!state.MomentumWins) {
      state.MomentumWins = [];
    }

    state.MomentumWins.push(win);
    Helpers.logActivity('ai_momentum_win', `AI logged momentum win: ${description}`, { winId: win.id, source: 'AI' });
    stateManager.update({ MomentumWins: state.MomentumWins });
    UI.showToast('Win Logged!', description, 'success');

    return { success: true, win };
  },

  // ============================================
  // NAVIGATION
  // ============================================

  /**
   * Navigate to a different screen
   * @param {string} screen - Screen name
   * @returns {Object} Result with success status
   */
  navigateTo(screen) {
    const validScreens = ['Home', 'Daily', 'AtoZ', 'Journal', 'Routines', 'FocusAreas', 'EightSteps', 'Statistics', 'Reflections', 'Timeline', 'Settings'];
    if (!validScreens.includes(screen)) {
      return { success: false, error: `Invalid screen. Available: ${validScreens.join(', ')}` };
    }

    navigate(screen);
    return { success: true, screen };
  },

  // ============================================
  // CONTEXT & SUGGESTIONS
  // ============================================

  /**
   * Get current context (delegates to AIContext)
   * @returns {Object} Full context
   */
  getContext() {
    return AIContext.getContext();
  },

  /**
   * Get quick context summary
   * @returns {Object} Condensed context
   */
  getQuickContext() {
    return AIContext.getQuickContext();
  },

  /**
   * Suggest day type based on history and current state
   * @returns {Object} Suggestion with reasoning
   */
  suggestDayType() {
    const streak = Helpers.getProgressStreak();
    const weeklyAvg = Helpers.getAverageProgress(7);
    const cogMode = CognitiveController.getMode();

    let suggestion = 'A';
    let reasoning = [];

    // Check cognitive mode
    if (cogMode === 'CLOSURE') {
      suggestion = 'B';
      reasoning.push('CLOSURE mode detected - suggest lighter day to focus on closing tasks');
    }

    // Check streak (burnout prevention)
    if (streak >= 5) {
      suggestion = 'B';
      reasoning.push(`${streak}-day streak - consider a lighter day to prevent burnout`);
    }

    // Check recent performance
    if (weeklyAvg < 50) {
      suggestion = 'B';
      reasoning.push(`Weekly average ${weeklyAvg}% - suggest reduced load`);
    } else if (weeklyAvg < 30) {
      suggestion = 'C';
      reasoning.push(`Weekly average ${weeklyAvg}% - suggest survival mode`);
    }

    // Check if it's a default A-day suggestion
    if (reasoning.length === 0) {
      reasoning.push('Good energy indicators - ready for full productivity');
    }

    return {
      suggestion,
      reasoning: reasoning.join('; '),
      metrics: {
        streak,
        weeklyAverage: weeklyAvg,
        cognitiveMode: cogMode
      }
    };
  },

  /**
   * Get next suggested action based on current state
   * @returns {Object} Suggested action with context
   */
  suggestNextAction() {
    const ctx = AIContext.getContext();
    const suggestions = [];

    // Check baseline goal
    if (!ctx.todayPlan.baselineGoal.completed && ctx.todayPlan.baselineGoal.text) {
      suggestions.push({
        priority: 1,
        action: 'Focus on baseline goal',
        details: ctx.todayPlan.baselineGoal.text,
        method: 'toggleGoal("baseline")'
      });
    }

    // Check pending time blocks
    const pendingBlocks = ctx.todayPlan.timeBlocksSummary.pending;
    if (pendingBlocks.length > 0) {
      suggestions.push({
        priority: 2,
        action: 'Complete next time block',
        details: `${pendingBlocks[0].time} - ${pendingBlocks[0].title}`,
        method: 'toggleTimeBlock(blockId)'
      });
    }

    // Check in-progress tasks
    if (ctx.tasks.byStatus.inProgress.length > 0) {
      const task = ctx.tasks.byStatus.inProgress[0];
      suggestions.push({
        priority: 3,
        action: 'Continue in-progress task',
        details: `${task.letter} - ${task.task}`,
        method: `completeTask("${task.id}")`
      });
    }

    // Check routines
    const incompleteRoutines = Object.entries(ctx.routines.todayCompletion)
      .filter(([_, status]) => !status.isComplete && status.percentage < 100);
    if (incompleteRoutines.length > 0) {
      const [routineName, status] = incompleteRoutines[0];
      suggestions.push({
        priority: 4,
        action: 'Continue routine',
        details: `${routineName} (${status.percentage}% complete)`,
        method: `completeRoutineStep("${routineName}", nextStepIndex)`
      });
    }

    return suggestions.sort((a, b) => a.priority - b.priority);
  },

  // ============================================
  // HELPER METHODS
  // ============================================

  _parseTime(timeStr) {
    // Handle various time formats
    const match = timeStr.match(/(\d{1,2}):(\d{2})\s*(AM|PM)?/i);
    if (!match) return 0;

    let hours = parseInt(match[1]);
    const minutes = parseInt(match[2]);
    const period = match[3]?.toUpperCase();

    if (period === 'PM' && hours !== 12) hours += 12;
    if (period === 'AM' && hours === 12) hours = 0;

    return hours * 60 + minutes;
  }
};

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = AIActions;
}
