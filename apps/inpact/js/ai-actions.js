// inPACT AI Actions Module
// A structured, governance-aware interface for an AI agent (or you, via console)
// to act on inPACT state. Every method returns { success, ... } and logs activity.
// Pairs with AIContext (read) and signals.js (backend-proposed actions w/ approval).

const AIActions = {
  _log(kind, msg, meta) {
    try {
      if (typeof Helpers !== 'undefined' && Helpers.logActivity) Helpers.logActivity(kind, msg, Object.assign({ source: 'AI' }, meta || {}));
    } catch (e) { /* non-fatal */ }
  },
  _save(slice) {
    stateManager.update(slice);
    if (typeof render === 'function') render();
  },

  /** Create a new A-Z task at the given letter. */
  createTask(letter, taskText, notes = '') {
    letter = String(letter || '').toUpperCase();
    if (!/^[A-Z]$/.test(letter)) return { success: false, error: 'Letter must be A-Z' };
    if ((state.AZTask || []).find(t => t.letter === letter)) return { success: false, error: `Letter ${letter} already used` };
    const task = { id: stateManager.generateId(), letter, task: String(taskText || '').trim(), notes: String(notes || '').trim(), status: 'Not Started', createdAt: new Date().toISOString() };
    if (!task.task) return { success: false, error: 'Task text required' };
    state.AZTask = (state.AZTask || []).concat(task).sort((a, b) => a.letter.localeCompare(b.letter));
    this._log('ai_task_created', `AI created ${letter}: ${task.task}`, { taskId: task.id });
    this._save({ AZTask: state.AZTask });
    if (typeof UI !== 'undefined') UI.showToast('Task created', `${letter}: ${task.task}`, 'success');
    return { success: true, task };
  },

  /** Mark a task complete by id. */
  completeTask(taskId) {
    const t = (state.AZTask || []).find(x => x.id === taskId);
    if (!t) return { success: false, error: 'Task not found' };
    t.status = 'Completed';
    this._log('ai_task_completed', `AI completed ${t.letter}: ${t.task}`, { taskId });
    this._save({ AZTask: state.AZTask });
    if (typeof UI !== 'undefined') UI.showToast('Task completed', `${t.letter}: ${t.task}`, 'success');
    return { success: true, task: t };
  },

  /** Update a task's status. */
  updateTaskStatus(taskId, status) {
    const valid = ['Not Started', 'In Progress', 'Completed'];
    if (!valid.includes(status)) return { success: false, error: `status must be one of: ${valid.join(', ')}` };
    const t = (state.AZTask || []).find(x => x.id === taskId);
    if (!t) return { success: false, error: 'Task not found' };
    t.status = status;
    this._log('ai_task_status', `AI set ${t.letter} -> ${status}`, { taskId, status });
    this._save({ AZTask: state.AZTask });
    return { success: true, task: t };
  },

  /** Set today's win target. */
  setWinTarget(text) {
    const today = stateManager.getTodayDate();
    if (!state.Today) state.Today = { mission: '', motto: '', daily: {} };
    if (!state.Today.daily) state.Today.daily = {};
    const day = state.Today.daily[today] || { date: today };
    day.winTarget = String(text || '').trim();
    state.Today.daily[today] = day;
    this._log('ai_win_target', `AI set win target: ${day.winTarget}`, {});
    this._save({ Today: state.Today });
    if (typeof UI !== 'undefined') UI.showToast('Win target set', day.winTarget, 'success');
    return { success: true, winTarget: day.winTarget };
  },

  /** Navigate to a screen. */
  navigateTo(screen) {
    const valid = ['Home', 'Daily', 'Tasks', 'History', 'Settings'];
    if (!valid.includes(screen)) return { success: false, error: `screen must be one of: ${valid.join(', ')}` };
    if (typeof navigate === 'function') navigate(screen);
    return { success: true, screen };
  },

  /** Refresh full context (delegates to AIContext). */
  getContext() { return AIContext.getContext(); },

  /**
   * Deterministic "next best move" from live governance + local state.
   * No LLM: this is the rules-based recommendation the HUD/AI surfaces.
   * @returns {Promise<{headline:string, detail:string, screen:string, tone:string}>}
   */
  async suggestNextAction() {
    const g = await AIContext._governance();
    const today = stateManager.getTodayDate();
    const ritual = (state.Today && state.Today.daily && state.Today.daily[today]) || {};
    const az = state.AZTask || [];
    const inProgress = az.filter(t => t.status === 'In Progress');
    const notStarted = az.filter(t => t.status === 'Not Started');

    if (g && g.mode === 'CLOSURE' && g.openLoops > 0) {
      return { headline: 'Close before you open', detail: g.primaryOrder || `${g.openLoops} open loop in CLOSURE mode. Finish it before starting new work.`, screen: 'Tasks', tone: 'closure' };
    }
    if (g && String(g.risk || '').toUpperCase() === 'HIGH') {
      return { headline: 'Protect focus', detail: 'Risk is HIGH. Pick one thing, finish it, avoid new commitments.', screen: 'Daily', tone: 'risk' };
    }
    if (!ritual.winTarget) {
      return { headline: "Set today's win target", detail: 'Name the one result that makes today count.', screen: 'Daily', tone: 'plan' };
    }
    if (inProgress.length) {
      return { headline: 'Finish what you started', detail: `${inProgress[0].letter}: ${inProgress[0].task}`, screen: 'Tasks', tone: 'execute' };
    }
    if (g && g.buildAllowed !== false && notStarted.length) {
      return { headline: 'Pick up the next task', detail: `${notStarted[0].letter}: ${notStarted[0].task}`, screen: 'Tasks', tone: 'execute' };
    }
    return { headline: "You're clear", detail: 'Nothing urgent. Keep moving on your win target.', screen: 'Home', tone: 'calm' };
  }
};

if (typeof module !== 'undefined' && module.exports) {
  module.exports = AIActions;
}

/**
 * Open the "Ask Atlas" panel: shows the next best move (read -> act) and lets you
 * copy your full state for an AI conversation. Built async so governance is live.
 */
async function openAtlasAI() {
  let sug = null;
  try { sug = await AIActions.suggestNextAction(); } catch (e) { /* offline */ }
  let prep = null;
  try { prep = await AtlasAPI.getPreparation(); } catch (e) { /* offline */ }

  const toneColor = {
    closure: '#f59e0b', risk: '#ef4444', plan: '#3b82f6', execute: '#22c55e', calm: 'var(--ip-gray-600)'
  };
  const accent = sug ? (toneColor[sug.tone] || 'var(--ip-black)') : 'var(--ip-gray-600)';

  const sugBlock = sug ? `
    <div style="border:1px solid var(--ip-gray-200);border-left:4px solid ${accent};border-radius:0.625rem;padding:1rem 1.125rem;margin-bottom:1.5rem;">
      <div style="font-size:0.625rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--ip-gray-600);margin-bottom:0.375rem;">Next best move</div>
      <div style="font-weight:700;font-size:1.0625rem;margin-bottom:0.25rem;">${UI.sanitize(sug.headline)}</div>
      <div style="font-size:0.875rem;color:var(--ip-gray-700);line-height:1.5;margin-bottom:0.875rem;">${UI.sanitize(sug.detail)}</div>
      <button class="td-btn" onclick="AIActions.navigateTo('${sug.screen}');UI.closeModal();" style="font-size:0.8125rem;padding:0.4375rem 0.875rem;">Go to ${UI.sanitize(sug.screen)}</button>
    </div>` : `
    <div style="border:1px solid var(--ip-gray-200);border-radius:0.625rem;padding:1rem 1.125rem;margin-bottom:1.5rem;color:var(--ip-gray-600);font-size:0.875rem;">
      Atlas governance is offline, so there's no live recommendation. You can still copy your state below.
    </div>`;

  const handleNextBlock = _renderHandleNext(prep);

  const content = `
    <div style="padding:1.5rem;max-width:30rem;">
      <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.25rem;">
        <i class="fas fa-satellite-dish" style="color:var(--ip-gray-600);"></i>
        <h2 style="font-size:1.25rem;font-weight:800;letter-spacing:-0.01em;">Ask Atlas</h2>
      </div>
      <p style="font-size:0.8125rem;color:var(--ip-gray-600);margin-bottom:1.25rem;">Your system's read on what to do next, plus a one-click export so any AI can see your real state.</p>

      ${sugBlock}

      ${handleNextBlock}

      <div style="font-size:0.625rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--ip-gray-600);margin-bottom:0.5rem;">Copy state for AI</div>
      <div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:0.75rem;">
        <button class="td-btn" onclick="AIContext.copyToClipboard('markdown')" style="font-size:0.8125rem;padding:0.4375rem 0.875rem;"><i class="fas fa-file-lines" style="margin-right:0.375rem;"></i>Markdown</button>
        <button class="td-btn-ghost" onclick="AIContext.copyToClipboard('prompt')" style="font-size:0.8125rem;padding:0.4375rem 0.875rem;">System prompt</button>
        <button class="td-btn-ghost" onclick="AIContext.copyToClipboard('json')" style="font-size:0.8125rem;padding:0.4375rem 0.875rem;">JSON</button>
      </div>
      <p style="font-size:0.75rem;color:var(--ip-gray-600);line-height:1.5;margin-bottom:1.25rem;">Paste into Claude to get help grounded in your tasks, today's plan, and live governance.</p>

      <div style="display:flex;justify-content:flex-end;">
        <button class="td-btn-ghost" onclick="UI.closeModal()" style="font-size:0.8125rem;">Close</button>
      </div>
    </div>`;

  UI.showModal(content);
}

/**
 * "Handle next" block: cortex's prepared queue (task/thread triage + top leverage move)
 * from /api/preparation. Read surface with a light "Mark done" on prepared tasks.
 */
function _renderHandleNext(prep) {
  const tasks = (prep && prep.taskTriage) || [];
  const threads = (prep && prep.threadTriage) || [];
  const moves = (prep && prep.leverageMoves) || [];

  let rows = '';
  tasks.slice(0, 3).forEach(t => {
    const id = t.task_id || t.entity_id || '';
    const label = t.task_title || t.label || 'Task';
    rows += `
      <div style="display:flex;align-items:center;justify-content:space-between;gap:0.75rem;padding:0.5rem 0;border-bottom:1px solid var(--ip-gray-100);">
        <span style="font-size:0.875rem;min-width:0;"><i class="fas fa-check" style="color:var(--ip-gray-300);margin-right:0.5rem;"></i>${UI.sanitize(label)}</span>
        ${id ? `<button class="td-btn" onclick="handlePreparedTask('${id}')" style="font-size:0.75rem;padding:0.25rem 0.625rem;flex-shrink:0;">Mark done</button>` : ''}
      </div>`;
  });
  threads.slice(0, 3).forEach(t => {
    const label = t.thread_title || t.label || 'Thread';
    rows += `
      <div style="padding:0.5rem 0;border-bottom:1px solid var(--ip-gray-100);font-size:0.875rem;">
        <i class="fas fa-reply" style="color:var(--ip-gray-300);margin-right:0.5rem;"></i>Reply: ${UI.sanitize(label)}
      </div>`;
  });
  if (moves.length) {
    const m = moves[0];
    const desc = m.description || m.rationale || '';
    rows += `
      <div style="padding:0.5rem 0;font-size:0.8125rem;color:var(--ip-gray-700);">
        <i class="fas fa-chess" style="color:var(--ip-gray-300);margin-right:0.5rem;"></i>Leverage: <strong>${UI.sanitize(m.label || m.move_id || 'move')}</strong>${desc ? ' . ' + UI.sanitize(desc) : ''}
      </div>`;
  }

  const body = rows || `<div style="font-size:0.8125rem;color:var(--ip-gray-600);">${prep ? 'Nothing queued. Your inbox is clear.' : 'Triage engine offline.'}</div>`;

  return `
    <div style="font-size:0.625rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--ip-gray-600);margin-bottom:0.5rem;">Handle next <span style="text-transform:none;letter-spacing:0;color:var(--ip-gray-300);">(prepared by cortex)</span></div>
    <div style="border:1px solid var(--ip-gray-200);border-radius:0.625rem;padding:0.25rem 1rem;margin-bottom:1.5rem;">${body}</div>`;
}

async function handlePreparedTask(taskId) {
  let ok = false;
  try { ok = await AtlasAPI.completeBackendTask(taskId); } catch (e) { ok = false; }
  if (typeof UI !== 'undefined') UI.showToast(ok ? 'Done' : 'Could not complete', ok ? 'Marked complete' : 'The backend rejected it', ok ? 'success' : 'error');
  openAtlasAI(); // refresh the panel
}
