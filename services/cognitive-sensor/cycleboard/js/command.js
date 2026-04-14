// CycleBoard Command Screen
// Single decision surface — mode + actions + tasks + ideas + leverage
// All data from delta-kernel API

const CommandScreen = {
  _apiBase: 'http://localhost:3001',
  _prepData: null,
  _notificationsSince: 0,
  _recentNotifications: [],

  _authHeaders() {
    const h = { 'Content-Type': 'application/json' };
    if (typeof stateManager !== 'undefined' && stateManager.apiKey) {
      h['Authorization'] = `Bearer ${stateManager.apiKey}`;
    }
    return h;
  },

  async render() {
    const main = document.getElementById('main-content');
    if (!main) return;

    const unified = CognitiveController.unified || {};
    const mode = unified.mode || '--';
    const closureRatio = unified.closure_ratio != null ? (unified.closure_ratio * 100).toFixed(0) : '--';
    const streakDays = unified.streak_days ?? 0;
    const openLoops = unified.open_loops ?? 0;
    const buildAllowed = unified.build_allowed !== false;
    const primaryOrder = unified.primary_order || 'Run refresh to get directive';

    // Load preparation data
    await this._loadPreparation();

    // Load top idea
    const topIdeas = BrainData.getTopIdeas(1);
    const topIdea = topIdeas[0] || null;

    // Get today's tasks from state
    const todayTasks = this._getTodayTasks();

    // Mode color map
    const modeColors = {
      RECOVER: 'from-red-900 to-red-800 border-red-600',
      CLOSURE: 'from-amber-900 to-amber-800 border-amber-600',
      MAINTENANCE: 'from-blue-900 to-blue-800 border-blue-600',
      BUILD: 'from-green-900 to-green-800 border-green-600',
      COMPOUND: 'from-purple-900 to-purple-800 border-purple-600',
      SCALE: 'from-cyan-900 to-cyan-800 border-cyan-600',
    };
    const modeColor = modeColors[mode] || modeColors.CLOSURE;

    const modeBadgeColors = {
      RECOVER: 'bg-red-600',
      CLOSURE: 'bg-amber-600',
      MAINTENANCE: 'bg-blue-600',
      BUILD: 'bg-green-600',
      COMPOUND: 'bg-purple-600',
      SCALE: 'bg-cyan-600',
    };

    main.innerHTML = `
      <div class="max-w-4xl mx-auto space-y-4 p-4">

        <!-- MODE HEADER -->
        <div class="bg-gradient-to-r ${modeColor} rounded-xl p-4 border">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-4">
              <span class="${modeBadgeColors[mode] || 'bg-gray-600'} px-4 py-2 rounded-lg text-xl font-black tracking-wider">${mode}</span>
              <div>
                <div class="text-sm opacity-75">Primary Order</div>
                <div class="text-lg font-semibold">${this._escapeHtml(primaryOrder)}</div>
              </div>
            </div>
            <div class="flex gap-6 text-center">
              <div>
                <div class="text-2xl font-bold">${closureRatio}%</div>
                <div class="text-xs opacity-75">Closure</div>
              </div>
              <div>
                <div class="text-2xl font-bold">${streakDays}</div>
                <div class="text-xs opacity-75">Streak</div>
              </div>
              <div>
                <div class="text-2xl font-bold ${openLoops > 5 ? 'text-red-400' : ''}">${openLoops}</div>
                <div class="text-xs opacity-75">Open Loops</div>
              </div>
            </div>
          </div>
          ${!buildAllowed ? '<div class="mt-2 text-xs text-red-300"><i class="fas fa-lock mr-1"></i> Build mode locked — close loops to unlock</div>' : ''}
        </div>

        <!-- PREPARED ACTIONS -->
        <div class="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-sm font-bold uppercase tracking-wider text-gray-400"><i class="fas fa-bolt mr-2 text-yellow-500"></i>Prepared Actions</h2>
            <span class="text-xs text-gray-500">${this._prepData ? 'Updated ' + DataFreshness.check(new Date(this._prepData.computed_at).toISOString()).ageText : 'Loading...'}</span>
          </div>
          ${this._renderPreparedActions()}
        </div>

        <!-- TODAY'S TASKS -->
        <div class="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-sm font-bold uppercase tracking-wider text-gray-400"><i class="fas fa-tasks mr-2 text-blue-500"></i>Today's Tasks</h2>
            <span class="text-xs text-gray-500">${todayTasks.length} tasks</span>
          </div>
          ${this._renderTasks(todayTasks)}
        </div>

        <div class="grid grid-cols-2 gap-4">
          <!-- TOP IDEA -->
          <div class="bg-gray-800 rounded-xl p-4 border border-gray-700">
            <h2 class="text-sm font-bold uppercase tracking-wider text-gray-400 mb-3"><i class="fas fa-lightbulb mr-2 text-yellow-400"></i>Top Idea</h2>
            ${topIdea ? `
              <div class="text-sm font-semibold mb-1">${this._escapeHtml(topIdea.title || topIdea.name || 'Untitled')}</div>
              <div class="text-xs text-gray-400 mb-2">${topIdea.tier || 'execute_now'} &middot; Score: ${((topIdea.priority_score || 0) * 100).toFixed(0)}%</div>
              <button onclick="CommandAPI.createTaskFromIdea('${this._escapeHtml(topIdea.title || topIdea.name || '')}')" class="text-xs px-3 py-1 bg-green-700 hover:bg-green-600 rounded transition">
                <i class="fas fa-plus mr-1"></i> Create Task
              </button>
            ` : '<div class="text-sm text-gray-500">No execute-now ideas. Run agent pipeline.</div>'}
          </div>

          <!-- LEVERAGE MOVE -->
          <div class="bg-gray-800 rounded-xl p-4 border border-gray-700">
            <h2 class="text-sm font-bold uppercase tracking-wider text-gray-400 mb-3"><i class="fas fa-chess mr-2 text-purple-400"></i>Leverage Move</h2>
            ${this._renderLeverageMove()}
          </div>
        </div>

        <!-- RECENT AUTO-ACTIONS -->
        ${this._renderNotifications()}

      </div>
    `;
  },

  _renderPreparedActions() {
    if (!this._prepData) {
      return '<div class="text-sm text-gray-500">Preparation engine starting up...</div>';
    }

    const actions = [];

    // Thread triage
    if (this._prepData.threadTriage?.length > 0) {
      for (const t of this._prepData.threadTriage.slice(0, 2)) {
        actions.push({
          label: `Reply: ${t.thread_title || t.label || 'Thread'}`,
          type: 'reply_message',
          icon: 'fa-reply',
          color: 'text-blue-400',
          id: t.thread_id || t.entity_id,
        });
      }
    }

    // Task triage
    if (this._prepData.taskTriage?.length > 0) {
      for (const t of this._prepData.taskTriage.slice(0, 2)) {
        actions.push({
          label: `Complete: ${t.task_title || t.label || 'Task'}`,
          type: 'complete_task',
          icon: 'fa-check',
          color: 'text-green-400',
          id: t.task_id || t.entity_id,
        });
      }
    }

    if (actions.length === 0) {
      return '<div class="text-sm text-gray-500">No prepared actions. System is idle.</div>';
    }

    return actions.slice(0, 3).map(a => `
      <div class="flex items-center justify-between py-2 border-b border-gray-700 last:border-0">
        <div class="flex items-center gap-2">
          <i class="fas ${a.icon} ${a.color}"></i>
          <span class="text-sm">${this._escapeHtml(a.label)}</span>
        </div>
        <div class="flex gap-2">
          <button onclick="CommandAPI.executeAction('${a.type}', '${a.id}')" class="text-xs px-3 py-1 bg-green-700 hover:bg-green-600 rounded transition">
            <i class="fas fa-check mr-1"></i> Do
          </button>
          <button onclick="CommandAPI.dismissAction('${a.id}')" class="text-xs px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded transition">
            <i class="fas fa-times"></i>
          </button>
        </div>
      </div>
    `).join('');
  },

  _renderTasks(tasks) {
    if (tasks.length === 0) {
      return '<div class="text-sm text-gray-500">No tasks for today. Add from A-Z or create from ideas.</div>';
    }

    return tasks.slice(0, 7).map(t => `
      <div class="flex items-center justify-between py-2 border-b border-gray-700 last:border-0">
        <div class="flex items-center gap-2">
          <button onclick="CommandAPI.completeTask('${t.id}')" class="w-5 h-5 rounded border ${t.done ? 'bg-green-600 border-green-500' : 'border-gray-500 hover:border-green-400'} flex items-center justify-center transition">
            ${t.done ? '<i class="fas fa-check text-xs"></i>' : ''}
          </button>
          <span class="text-sm ${t.done ? 'line-through text-gray-500' : ''}">${this._escapeHtml(t.text || t.title || '')}</span>
        </div>
        ${t.priority ? `<span class="text-xs px-2 py-0.5 rounded ${t.priority === 'HIGH' ? 'bg-red-900 text-red-300' : t.priority === 'MEDIUM' ? 'bg-yellow-900 text-yellow-300' : 'bg-gray-700 text-gray-400'}">${t.priority}</span>` : ''}
      </div>
    `).join('');
  },

  _renderLeverageMove() {
    if (!this._prepData?.leverageMoves?.length) {
      return '<div class="text-sm text-gray-500">No leverage move computed yet.</div>';
    }

    const move = this._prepData.leverageMoves[0];
    return `
      <div class="text-sm font-semibold mb-1">${this._escapeHtml(move.label || move.move_id || 'Move')}</div>
      <div class="text-xs text-gray-400">${this._escapeHtml(move.description || move.rationale || '')}</div>
    `;
  },

  _renderNotifications() {
    if (this._recentNotifications.length === 0) return '';

    return `
      <div class="bg-gray-800/50 rounded-xl p-3 border border-gray-700/50">
        <h2 class="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2"><i class="fas fa-robot mr-1"></i>Auto-Actions</h2>
        ${this._recentNotifications.slice(0, 3).map(n => `
          <div class="text-xs text-gray-400 py-1">
            <i class="fas fa-check-circle text-green-600 mr-1"></i>
            ${this._escapeHtml(n.type || '')} — ${this._escapeHtml(n.data?.title || '')}
            <span class="text-gray-600">${DataFreshness.check(n.ts).ageText}</span>
          </div>
        `).join('')}
      </div>
    `;
  },

  _getTodayTasks() {
    if (!state?.tasks) return [];
    const today = new Date().toISOString().split('T')[0];
    return state.tasks.filter(t => {
      if (t.date === today) return true;
      if (t.scheduledDate === today) return true;
      return false;
    }).sort((a, b) => {
      if (a.done !== b.done) return a.done ? 1 : -1;
      const priorityOrder = { HIGH: 0, MEDIUM: 1, LOW: 2 };
      return (priorityOrder[a.priority] ?? 2) - (priorityOrder[b.priority] ?? 2);
    });
  },

  async _loadPreparation() {
    try {
      const res = await fetch(`${this._apiBase}/api/preparation`, {
        headers: this._authHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        this._prepData = data.data;
      }
    } catch (_) {}

    // Load recent notifications
    try {
      const res = await fetch(`${this._apiBase}/api/notifications?types=AUTO_EXECUTED,CLOSURE_PROCESSED,IDEA_AUTO_PROMOTED,TASK_AUTO_ARCHIVED`, {
        headers: this._authHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        this._recentNotifications = (data.events || []).slice(-5).reverse();
      }
    } catch (_) {}
  },

  _escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  },
};

// CommandAPI — inline actions from Command screen
const CommandAPI = {
  _apiBase: 'http://localhost:3001',

  _authHeaders() {
    const h = { 'Content-Type': 'application/json' };
    if (typeof stateManager !== 'undefined' && stateManager.apiKey) {
      h['Authorization'] = `Bearer ${stateManager.apiKey}`;
    }
    return h;
  },

  async completeTask(taskId) {
    // Complete in local state
    if (state?.tasks) {
      const task = state.tasks.find(t => t.id === taskId);
      if (task) {
        task.done = true;
        stateManager.update({ tasks: state.tasks });
      }
    }

    // Also complete in delta-kernel
    try {
      await fetch(`${this._apiBase}/api/tasks/${taskId}`, {
        method: 'PUT',
        headers: this._authHeaders(),
        body: JSON.stringify({ status: 'DONE' }),
      });
    } catch (_) {}

    if (state.screen === 'Command') CommandScreen.render();
  },

  async closeLoop(loopId, title) {
    try {
      await fetch(`${this._apiBase}/api/law/close_loop`, {
        method: 'POST',
        headers: this._authHeaders(),
        body: JSON.stringify({ loop_id: loopId, title, outcome: 'closed' }),
      });
    } catch (_) {}

    if (state.screen === 'Command') CommandScreen.render();
  },

  async createTaskFromIdea(title) {
    if (!title) return;

    try {
      await fetch(`${this._apiBase}/api/tasks`, {
        method: 'POST',
        headers: this._authHeaders(),
        body: JSON.stringify({
          title,
          status: 'OPEN',
          priority: 'MEDIUM',
          source: 'command_screen',
        }),
      });
    } catch (_) {}

    // Also add to local state
    if (state?.tasks) {
      const today = new Date().toISOString().split('T')[0];
      state.tasks.push({
        id: `cmd-${Date.now()}`,
        text: title,
        date: today,
        done: false,
        priority: 'MEDIUM',
      });
      stateManager.update({ tasks: state.tasks });
    }

    if (state.screen === 'Command') CommandScreen.render();
  },

  async executeAction(type, entityId) {
    if (type === 'complete_task') {
      await this.completeTask(entityId);
    } else if (type === 'reply_message') {
      // Open thread in a new context (future: inline compose)
      console.log(`[Command] Reply action for ${entityId} — requires compose UI`);
    }
  },

  async dismissAction(entityId) {
    // For now just re-render (future: mark as dismissed in API)
    if (state.screen === 'Command') CommandScreen.render();
  },
};
