// CycleBoard AI Context Module
// Generates comprehensive context snapshots for AI agents

const AIContext = {
  /**
   * Generates a complete context snapshot for AI consumption
   * @returns {Object} Full application state and computed data
   */
  getContext() {
    const today = stateManager.getTodayDate();
    const dayPlan = Helpers.getDayPlan(today);
    const progress = Helpers.calculateDailyProgress(today);

    return {
      // Metadata
      _meta: {
        generatedAt: new Date().toISOString(),
        version: state.version || '2.0',
        source: 'CycleBoard AI Context'
      },

      // Current date/time context
      temporal: {
        today: today,
        todayFormatted: Helpers.formatDate(today),
        dayOfWeek: new Date().toLocaleDateString('en-US', { weekday: 'long' }),
        currentTime: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
      },

      // Current UI state
      navigation: {
        currentScreen: state.screen,
        availableScreens: ['Home', 'Daily', 'AtoZ', 'Journal', 'Routines', 'FocusAreas', 'EightSteps', 'Statistics', 'Reflections', 'Timeline', 'Settings']
      },

      // Today's plan (detailed)
      todayPlan: {
        date: dayPlan.date,
        dayType: dayPlan.day_type,
        dayTypeDescription: this._getDayTypeDescription(dayPlan.day_type),
        baselineGoal: dayPlan.baseline_goal,
        stretchGoal: dayPlan.stretch_goal,
        timeBlocks: dayPlan.time_blocks,
        timeBlocksSummary: {
          total: dayPlan.time_blocks.length,
          completed: dayPlan.time_blocks.filter(b => b.completed).length,
          pending: dayPlan.time_blocks.filter(b => !b.completed).map(b => ({ time: b.time, title: b.title }))
        },
        routinesCompleted: dayPlan.routines_completed,
        notes: dayPlan.notes,
        rating: dayPlan.rating
      },

      // Progress metrics
      progress: {
        overall: progress.overall,
        breakdown: progress.breakdown,
        timeBlocks: progress.timeBlocks,
        goals: progress.goals,
        routines: progress.routines,
        focusAreas: progress.focusAreas,
        streak: Helpers.getProgressStreak(),
        weeklyAverage: Helpers.getAverageProgress(7)
      },

      // A-Z Tasks (monthly tasks)
      tasks: {
        all: state.AZTask,
        summary: {
          total: state.AZTask.length,
          notStarted: state.AZTask.filter(t => t.status === TASK_STATUS.NOT_STARTED).length,
          inProgress: state.AZTask.filter(t => t.status === TASK_STATUS.IN_PROGRESS).length,
          completed: state.AZTask.filter(t => t.status === TASK_STATUS.COMPLETED).length,
          completionPercentage: Helpers.calculateCompletionPercentage()
        },
        byStatus: {
          notStarted: state.AZTask.filter(t => t.status === TASK_STATUS.NOT_STARTED),
          inProgress: state.AZTask.filter(t => t.status === TASK_STATUS.IN_PROGRESS),
          completed: state.AZTask.filter(t => t.status === TASK_STATUS.COMPLETED)
        },
        availableLetters: this._getAvailableLetters()
      },

      // Routines
      routines: {
        definitions: state.Routine,
        routineNames: Object.keys(state.Routine),
        todayCompletion: this._getRoutineCompletionStatus(dayPlan)
      },

      // Focus Areas
      focusAreas: {
        areas: state.FocusArea,
        summary: state.FocusArea.map(area => ({
          name: area.name,
          taskCount: area.tasks?.length || 0,
          completedCount: area.tasks?.filter(t => t.completed).length || 0
        }))
      },

      // Journal (recent entries)
      journal: {
        totalEntries: state.Journal.length,
        recentEntries: state.Journal.slice(-10).reverse(),
        entriesByType: {
          free: state.Journal.filter(j => j.entryType === 'free').length,
          weekly: state.Journal.filter(j => j.entryType === 'weekly').length,
          gratitude: state.Journal.filter(j => j.entryType === 'gratitude').length
        }
      },

      // Activity history
      history: {
        recentActivity: (state.History?.timeline || []).slice(-20).reverse(),
        completedTasksCount: state.History?.completedTasks?.length || 0,
        streak: state.History?.streak || 0
      },

      // Weekly statistics
      weeklyStats: Helpers.getWeeklyStats(),

      // Progress history (last 7 days)
      progressHistory: Helpers.getProgressHistory(7),

      // Settings
      settings: state.Settings,

      // Cognitive system (if active)
      cognitive: CognitiveController.initialized ? {
        mode: CognitiveController.getMode(),
        risk: CognitiveController.getRisk(),
        openLoops: CognitiveController.getOpenLoops(),
        isClosureMode: CognitiveController.isClosureMode()
      } : { mode: 'OFFLINE', risk: 'UNKNOWN', openLoops: [], isClosureMode: false },

      // Day type templates (for reference)
      dayTypeTemplates: state.DayTypeTemplates,

      // Reflections summary
      reflections: {
        weekly: state.Reflections?.weekly?.length || 0,
        monthly: state.Reflections?.monthly?.length || 0,
        quarterly: state.Reflections?.quarterly?.length || 0,
        yearly: state.Reflections?.yearly?.length || 0,
        recent: this._getRecentReflections()
      },

      // Momentum wins (today)
      momentumWins: this._getTodayMomentumWins()
    };
  },

  /**
   * Get a minimal context for quick AI queries
   * @returns {Object} Condensed context
   */
  getQuickContext() {
    const today = stateManager.getTodayDate();
    const dayPlan = Helpers.getDayPlan(today);
    const progress = Helpers.calculateDailyProgress(today);

    return {
      today: today,
      dayType: dayPlan.day_type,
      overallProgress: progress.overall,
      tasksInProgress: state.AZTask.filter(t => t.status === TASK_STATUS.IN_PROGRESS).length,
      pendingTimeBlocks: dayPlan.time_blocks.filter(b => !b.completed).length,
      cognitiveMode: CognitiveController.getMode(),
      streak: Helpers.getProgressStreak()
    };
  },

  /**
   * Generate a system prompt for AI with current context
   * @returns {string} System prompt with embedded context
   */
  getSystemPrompt() {
    const ctx = this.getContext();

    return `# CycleBoard AI Assistant Context

You are an AI assistant integrated with CycleBoard, a productivity/bullet journal app.

## Your Capabilities
You can:
- View the user's tasks, goals, routines, and journal
- Create, update, and complete A-Z tasks
- Set day types (A/B/C) and daily goals
- Add time blocks and journal entries
- Track routine completion
- Provide productivity insights and suggestions

## Day Types
- A Day: High energy, optimal productivity - full schedule
- B Day: Low energy, reduced expectations - lighter workload
- C Day: Chaos/survival mode - bare minimum, one priority only

## Task Status Values
- "Not Started" - Task hasn't been begun
- "In Progress" - Currently working on
- "Completed" - Task finished

## Current State Summary
- Date: ${ctx.temporal.todayFormatted} (${ctx.temporal.dayOfWeek})
- Day Type: ${ctx.todayPlan.dayType} (${ctx.todayPlan.dayTypeDescription})
- Overall Progress: ${ctx.progress.overall}%
- Streak: ${ctx.progress.streak} days
- Cognitive Mode: ${ctx.cognitive.mode}

## Today's Goals
- Baseline: ${ctx.todayPlan.baselineGoal.text} (${ctx.todayPlan.baselineGoal.completed ? 'DONE' : 'pending'})
- Stretch: ${ctx.todayPlan.stretchGoal.text} (${ctx.todayPlan.stretchGoal.completed ? 'DONE' : 'pending'})

## Tasks Summary
- Total: ${ctx.tasks.summary.total}
- Not Started: ${ctx.tasks.summary.notStarted}
- In Progress: ${ctx.tasks.summary.inProgress}
- Completed: ${ctx.tasks.summary.completed}

## Pending Time Blocks
${ctx.todayPlan.timeBlocksSummary.pending.map(b => `- ${b.time}: ${b.title}`).join('\n') || 'None'}

## Available Actions
Use AIActions object methods:
- AIActions.createTask(letter, task, notes)
- AIActions.completeTask(taskId)
- AIActions.updateTaskStatus(taskId, status)
- AIActions.setDayType('A'|'B'|'C')
- AIActions.setGoals(baseline, stretch)
- AIActions.addTimeBlock(time, title, duration)
- AIActions.addJournalEntry(title, content, type)
- AIActions.completeRoutineStep(routineName, stepIndex)
- AIActions.toggleTimeBlock(blockId)
- AIActions.getContext() - refresh full context

## Guidelines
1. Respect the user's energy level (day type)
2. Don't overwhelm - suggest 1-3 actions at a time
3. Celebrate completions and progress
4. Notice patterns in activity history
5. Suggest realistic goals based on history
6. In CLOSURE mode, prioritize completing existing tasks over creating new ones`;
  },

  // Helper methods

  _getDayTypeDescription(type) {
    const descriptions = {
      'A': 'Optimal day - full energy, maximum output',
      'B': 'Low energy day - conserve energy, focus on essentials',
      'C': 'Chaos day - survival mode, one priority only'
    };
    return descriptions[type] || 'Unknown';
  },

  _getAvailableLetters() {
    const usedLetters = state.AZTask.map(t => t.letter);
    const allLetters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
    return allLetters.filter(l => !usedLetters.includes(l));
  },

  _getRoutineCompletionStatus(dayPlan) {
    const status = {};
    Object.keys(state.Routine).forEach(routineName => {
      const steps = state.Routine[routineName];
      const completedSteps = dayPlan.routines_completed?.[routineName]?.steps || {};
      const completedCount = Object.values(completedSteps).filter(v => v).length;
      status[routineName] = {
        totalSteps: steps.length,
        completedSteps: completedCount,
        percentage: steps.length ? Math.round((completedCount / steps.length) * 100) : 0,
        isComplete: dayPlan.routines_completed?.[routineName]?.completed || false
      };
    });
    return status;
  },

  _getRecentReflections() {
    const all = [];
    ['weekly', 'monthly', 'quarterly', 'yearly'].forEach(period => {
      const reflections = state.Reflections?.[period] || [];
      reflections.slice(-2).forEach(r => {
        all.push({ ...r, period });
      });
    });
    return all.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)).slice(0, 5);
  },

  _getTodayMomentumWins() {
    const today = stateManager.getTodayDate();
    return (state.MomentumWins || []).filter(w => w.date === today);
  },

  /**
   * Generate a human-readable markdown snapshot for clipboard
   * Optimized for pasting into an LLM chat
   * @returns {string} Markdown formatted context
   */
  getClipboardSnapshot() {
    const ctx = this.getContext();
    const dayPlan = ctx.todayPlan;

    // Build markdown snapshot
    let md = `# CycleBoard Context Snapshot
*Generated: ${ctx.temporal.todayFormatted} at ${ctx.temporal.currentTime}*

---

## Today's Overview
- **Date:** ${ctx.temporal.todayFormatted} (${ctx.temporal.dayOfWeek})
- **Day Type:** ${dayPlan.dayType}-Day (${dayPlan.dayTypeDescription})
- **Overall Progress:** ${ctx.progress.overall}%
- **Streak:** ${ctx.progress.streak} days

## Daily Goals
| Goal | Status |
|------|--------|
| **Baseline:** ${dayPlan.baselineGoal.text || 'Not set'} | ${dayPlan.baselineGoal.completed ? '✅ Done' : '⬜ Pending'} |
| **Stretch:** ${dayPlan.stretchGoal.text || 'Not set'} | ${dayPlan.stretchGoal.completed ? '✅ Done' : '⬜ Pending'} |

## Time Blocks (${dayPlan.timeBlocksSummary.completed}/${dayPlan.timeBlocksSummary.total} complete)
`;

    if (dayPlan.timeBlocks.length > 0) {
      dayPlan.timeBlocks.forEach(block => {
        md += `- ${block.completed ? '✅' : '⬜'} **${block.time}** - ${block.title}\n`;
      });
    } else {
      md += `*No time blocks scheduled*\n`;
    }

    md += `
## A-Z Tasks (${ctx.tasks.summary.completed}/${ctx.tasks.summary.total} complete)
`;

    // Group tasks by status
    if (ctx.tasks.byStatus.inProgress.length > 0) {
      md += `\n### 🔄 In Progress\n`;
      ctx.tasks.byStatus.inProgress.forEach(t => {
        md += `- **${t.letter}:** ${t.task}${t.notes ? ` *(${t.notes})*` : ''}\n`;
      });
    }

    if (ctx.tasks.byStatus.notStarted.length > 0) {
      md += `\n### ⬜ Not Started\n`;
      ctx.tasks.byStatus.notStarted.forEach(t => {
        md += `- **${t.letter}:** ${t.task}\n`;
      });
    }

    if (ctx.tasks.byStatus.completed.length > 0) {
      md += `\n### ✅ Completed\n`;
      ctx.tasks.byStatus.completed.forEach(t => {
        md += `- **${t.letter}:** ${t.task}\n`;
      });
    }

    // Routines
    md += `\n## Routines\n`;
    Object.entries(ctx.routines.todayCompletion).forEach(([name, status]) => {
      const icon = status.isComplete ? '✅' : (status.percentage > 0 ? '🔄' : '⬜');
      md += `- ${icon} **${name}:** ${status.completedSteps}/${status.totalSteps} steps (${status.percentage}%)\n`;
    });

    // Progress breakdown
    md += `\n## Progress Breakdown\n`;
    ctx.progress.breakdown.forEach(item => {
      const pct = item.percentage;
      const bar = '█'.repeat(Math.floor(pct / 10)) + '░'.repeat(10 - Math.floor(pct / 10));
      md += `- **${item.label}:** ${bar} ${pct}% (${item.completed}/${item.total})\n`;
    });

    // Weekly stats
    md += `\n## Weekly Stats
- Days tracked: ${ctx.weeklyStats.total}
- Goals met: ${ctx.weeklyStats.completed}
- Success rate: ${ctx.weeklyStats.percentage}%
`;

    // Cognitive mode if active
    if (ctx.cognitive.mode !== 'OFFLINE') {
      md += `\n## Cognitive State
- **Mode:** ${ctx.cognitive.mode}
- **Risk Level:** ${ctx.cognitive.risk}
- **Open Loops:** ${ctx.cognitive.openLoops.length}
`;
    }

    // Recent activity
    if (ctx.history.recentActivity.length > 0) {
      md += `\n## Recent Activity (last 5)\n`;
      ctx.history.recentActivity.slice(0, 5).forEach(activity => {
        const time = new Date(activity.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        md += `- *${time}* - ${activity.description}\n`;
      });
    }

    // Recent journal if any
    if (ctx.journal.recentEntries.length > 0) {
      md += `\n## Recent Journal Entries\n`;
      ctx.journal.recentEntries.slice(0, 3).forEach(entry => {
        const date = new Date(entry.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        md += `- **${entry.title}** (${date}) - ${entry.entryType}\n`;
      });
    }

    md += `\n---
*Available letters for new tasks: ${ctx.tasks.availableLetters.slice(0, 10).join(', ')}${ctx.tasks.availableLetters.length > 10 ? '...' : ''}*
`;

    return md;
  },

  /**
   * Copy context snapshot to clipboard
   * @param {string} format - 'markdown', 'json', or 'prompt'
   * @returns {Promise<boolean>} Success status
   */
  async copyToClipboard(format = 'markdown') {
    let content;

    switch (format) {
      case 'json':
        content = JSON.stringify(this.getContext(), null, 2);
        break;
      case 'prompt':
        content = this.getSystemPrompt();
        break;
      case 'markdown':
      default:
        content = this.getClipboardSnapshot();
        break;
    }

    try {
      await navigator.clipboard.writeText(content);
      UI.showToast('Copied!', `${format.charAt(0).toUpperCase() + format.slice(1)} snapshot copied to clipboard`, 'success');
      return true;
    } catch (err) {
      console.error('Failed to copy:', err);
      UI.showToast('Copy Failed', 'Could not access clipboard', 'error');
      return false;
    }
  }
};

// Global function to show copy context modal
function showCopyContextModal() {
  const content = `
    <div class="p-6">
      <div class="flex items-center gap-3 mb-4">
        <div class="w-12 h-12 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
          <i class="fas fa-copy text-blue-600 dark:text-blue-400 text-xl"></i>
        </div>
        <div>
          <h2 class="text-xl font-bold dark:text-white">Copy AI Context</h2>
          <p class="text-sm text-slate-500 dark:text-gray-400">Choose a format to copy to clipboard</p>
        </div>
      </div>

      <div class="space-y-3 mb-6">
        <button onclick="AIContext.copyToClipboard('markdown');UI.closeModal();"
                class="w-full flex items-center gap-4 p-4 border dark:border-gray-600 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700 transition text-left">
          <div class="w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
            <i class="fas fa-file-alt text-purple-600 dark:text-purple-400"></i>
          </div>
          <div class="flex-1">
            <div class="font-semibold dark:text-white">Markdown Snapshot</div>
            <div class="text-sm text-slate-500 dark:text-gray-400">Human-readable format, great for chat</div>
          </div>
          <i class="fas fa-chevron-right text-slate-400"></i>
        </button>

        <button onclick="AIContext.copyToClipboard('prompt');UI.closeModal();"
                class="w-full flex items-center gap-4 p-4 border dark:border-gray-600 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700 transition text-left">
          <div class="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
            <i class="fas fa-robot text-green-600 dark:text-green-400"></i>
          </div>
          <div class="flex-1">
            <div class="font-semibold dark:text-white">System Prompt</div>
            <div class="text-sm text-slate-500 dark:text-gray-400">Optimized for AI system prompts</div>
          </div>
          <i class="fas fa-chevron-right text-slate-400"></i>
        </button>

        <button onclick="AIContext.copyToClipboard('json');UI.closeModal();"
                class="w-full flex items-center gap-4 p-4 border dark:border-gray-600 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700 transition text-left">
          <div class="w-10 h-10 rounded-lg bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center">
            <i class="fas fa-code text-orange-600 dark:text-orange-400"></i>
          </div>
          <div class="flex-1">
            <div class="font-semibold dark:text-white">JSON Data</div>
            <div class="text-sm text-slate-500 dark:text-gray-400">Full structured data for processing</div>
          </div>
          <i class="fas fa-chevron-right text-slate-400"></i>
        </button>
      </div>

      <div class="flex justify-end">
        <button onclick="UI.closeModal()" class="px-4 py-2 text-slate-500 dark:text-gray-400 hover:text-slate-700 dark:hover:text-gray-200">
          Cancel
        </button>
      </div>
    </div>
  `;
  UI.showModal(content);
}

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = AIContext;
}
