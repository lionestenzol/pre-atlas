// CycleBoard Functions Module
// All action functions for the application

// Search debounce timer
let searchDebounceTimer = null;

// Filter state accessors - stored in app state for persistence
function getAzFilter() {
  return state.UI?.azFilter || 'all';
}

function setAzFilter(value) {
  if (!state.UI) state.UI = {};
  state.UI.azFilter = value;
}

function getAzSearch() {
  return state.UI?.azSearch || '';
}

function setAzSearch(value) {
  if (!state.UI) state.UI = {};
  state.UI.azSearch = value;
}

// Debounce utility function
function debounce(func, delay) {
  let timeoutId;
  return function(...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func.apply(this, args), delay);
  };
}
function completeTask(id) {
  const task = state.AZTask.find(t => t.id === id);
  if (task) {
    task.status = 'Completed';
    state.History.completedTasks.push({
      taskId: task.id,
      completedAt: new Date().toISOString()
    });
    Helpers.logActivity('task_completed', `Completed A-Z Task: ${task.letter} - ${task.task}`, { taskId: task.id });
    stateManager.update({ AZTask: state.AZTask, History: state.History });
    render();
    UI.showToast('Task Completed', `${task.letter} – ${task.task}`, 'success');
  }
}

function deleteTask(id) {
  const task = state.AZTask.find(t => t.id === id);
  if (task && confirm(`Delete task ${task.letter} – ${task.task}?`)) {
    Helpers.logActivity('task_deleted', `Deleted A-Z Task: ${task.letter} - ${task.task}`, { taskId: task.id });
    state.AZTask = state.AZTask.filter(t => t.id !== id);
    stateManager.update({ AZTask: state.AZTask });
    render();
    UI.showToast('Task Deleted', `${task.letter} – ${task.task}`, 'warning');
  }
}

function setDayType(type, applyTemplate = null) {
  const todayPlan = Helpers.getDayPlan();
  const oldType = todayPlan.day_type;

  // If no change in type and no template action pending, skip
  if (oldType === type && applyTemplate === null) {
    return;
  }

  // If switching to a different day type and no template decision made, show modal
  if (oldType !== type && applyTemplate === null) {
    showApplyTemplateModal(type, oldType);
    return;
  }

  // Now actually change the type
  todayPlan.day_type = type;

  // Apply template if requested
  if (applyTemplate === true) {
    applyDayTypeTemplate(todayPlan, type);
  }

  // Log the change
  if (oldType !== type || applyTemplate !== null) {
    Helpers.logActivity('day_type_changed', `Changed day type to ${type}-Day`, { from: oldType, to: type, templateApplied: applyTemplate });
  }

  state.DayPlans[todayPlan.date] = todayPlan;
  stateManager.update({ DayPlans: state.DayPlans });
  render();
}

function showApplyTemplateModal(newType, oldType) {
  const template = state.DayTypeTemplates?.[newType];
  if (!template) {
    // No template, just apply the change
    setDayType(newType, false);
    return;
  }

  const content = `
    <div class="p-6">
      <div class="flex items-center gap-3 mb-4">
        <div class="w-12 h-12 rounded-full flex items-center justify-center text-2xl font-bold ${
          newType === 'A' ? 'bg-green-100 text-green-700' :
          newType === 'B' ? 'bg-yellow-100 text-yellow-700' :
          'bg-red-100 text-red-700'
        }">
          ${newType}
        </div>
        <div>
          <h2 class="text-xl font-bold dark:text-white">${template.name}</h2>
          <p class="text-sm text-slate-500 dark:text-gray-400">${template.description}</p>
        </div>
      </div>

      <div class="bg-slate-50 dark:bg-gray-700 rounded-lg p-4 mb-4">
        <h3 class="font-semibold text-sm mb-2 dark:text-gray-300">This template includes:</h3>
        <ul class="text-sm space-y-1 text-slate-600 dark:text-gray-400">
          <li><i class="fas fa-clock mr-2 text-blue-500"></i>${template.timeBlocks.length} time blocks</li>
          <li><i class="fas fa-list-check mr-2 text-green-500"></i>${template.routines.length} routines: ${template.routines.join(', ')}</li>
          <li><i class="fas fa-bullseye mr-2 text-purple-500"></i>Baseline: ${template.goals.baseline}</li>
          <li><i class="fas fa-rocket mr-2 text-amber-500"></i>Stretch: ${template.goals.stretch}</li>
        </ul>
      </div>

      <p class="text-sm text-slate-600 dark:text-gray-400 mb-4">
        Would you like to apply this schedule template? This will replace your current time blocks.
      </p>

      <div class="flex gap-3">
        <button onclick="setDayType('${newType}', true);UI.closeModal();" class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          <i class="fas fa-check mr-2"></i>Apply Template
        </button>
        <button onclick="setDayType('${newType}', false);UI.closeModal();" class="flex-1 px-4 py-2 border dark:border-gray-600 dark:text-gray-300 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700">
          Just Change Type
        </button>
        <button onclick="UI.closeModal()" class="px-4 py-2 text-slate-500 dark:text-gray-400 hover:text-slate-700">
          Cancel
        </button>
      </div>
    </div>
  `;

  UI.showModal(content);
}

function applyDayTypeTemplate(dayPlan, type) {
  const template = state.DayTypeTemplates?.[type];
  if (!template) return;

  // Apply time blocks
  dayPlan.time_blocks = template.timeBlocks.map(block => ({
    id: stateManager.generateId(),
    time: block.time,
    title: block.title,
    duration: block.duration,
    completed: false
  }));

  // Apply goals
  dayPlan.baseline_goal = { text: template.goals.baseline, completed: false };
  dayPlan.stretch_goal = { text: template.goals.stretch, completed: false };

  // Mark which routines are active for this day type
  dayPlan.activeRoutines = template.routines;

  UI.showToast('Template Applied', `${template.name} schedule loaded`, 'success');
}

// Use UI.sanitize for HTML escaping - this alias is kept for backwards compatibility
const escapeHtml = UI.sanitize;

function openDayTypeTemplateEditor(type) {
  const template = state.DayTypeTemplates?.[type] || {
    name: `${type}-Day`,
    description: '',
    timeBlocks: [],
    routines: [],
    goals: { baseline: '', stretch: '' }
  };

  const colors = {
    A: { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-300', darkBg: 'dark:bg-green-900/30', darkText: 'dark:text-green-400' },
    B: { bg: 'bg-yellow-100', text: 'text-yellow-700', border: 'border-yellow-300', darkBg: 'dark:bg-yellow-900/30', darkText: 'dark:text-yellow-400' },
    C: { bg: 'bg-red-100', text: 'text-red-700', border: 'border-red-300', darkBg: 'dark:bg-red-900/30', darkText: 'dark:text-red-400' }
  };
  const color = colors[type];

  const allRoutineNames = Object.keys(state.Routine || {});

  const content = `
    <div class="p-6 max-h-[80vh] overflow-y-auto">
      <div class="flex items-center gap-3 mb-6">
        <div class="w-12 h-12 rounded-full flex items-center justify-center text-2xl font-bold ${color.bg} ${color.text} ${color.darkBg} ${color.darkText}">
          ${type}
        </div>
        <div class="flex-1">
          <h2 class="text-xl font-bold dark:text-white">Edit ${type}-Day Template</h2>
          <p class="text-sm text-slate-500 dark:text-gray-400">Customize schedule, routines, and goals</p>
        </div>
      </div>

      <!-- Basic Info -->
      <div class="mb-6">
        <h3 class="font-semibold text-sm mb-2 dark:text-gray-300">Template Info</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-slate-500 dark:text-gray-400 mb-1">Name</label>
            <input type="text" id="template-name" value="${escapeHtml(template.name)}"
              class="w-full px-3 py-2 border dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label class="block text-xs text-slate-500 dark:text-gray-400 mb-1">Description</label>
            <input type="text" id="template-description" value="${escapeHtml(template.description)}"
              class="w-full px-3 py-2 border dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white focus:ring-2 focus:ring-blue-500" />
          </div>
        </div>
      </div>

      <!-- Goals -->
      <div class="mb-6">
        <h3 class="font-semibold text-sm mb-2 dark:text-gray-300">Goals</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-slate-500 dark:text-gray-400 mb-1"><i class="fas fa-bullseye mr-1 text-purple-500"></i>Baseline Goal</label>
            <input type="text" id="template-baseline" value="${escapeHtml(template.goals?.baseline || '')}"
              class="w-full px-3 py-2 border dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label class="block text-xs text-slate-500 dark:text-gray-400 mb-1"><i class="fas fa-rocket mr-1 text-amber-500"></i>Stretch Goal</label>
            <input type="text" id="template-stretch" value="${escapeHtml(template.goals?.stretch || '')}"
              class="w-full px-3 py-2 border dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white focus:ring-2 focus:ring-blue-500" />
          </div>
        </div>
      </div>

      <!-- Routines -->
      <div class="mb-6">
        <h3 class="font-semibold text-sm mb-2 dark:text-gray-300">Active Routines</h3>
        <div class="flex flex-wrap gap-2" id="template-routines">
          ${allRoutineNames.map(name => `
            <label class="flex items-center gap-2 px-3 py-2 border dark:border-gray-600 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-gray-700">
              <input type="checkbox" value="${name}" ${template.routines?.includes(name) ? 'checked' : ''}
                class="rounded text-blue-600 focus:ring-blue-500" />
              <span class="text-sm dark:text-gray-300">${name}</span>
            </label>
          `).join('')}
        </div>
      </div>

      <!-- Time Blocks -->
      <div class="mb-6">
        <div class="flex justify-between items-center mb-2">
          <h3 class="font-semibold text-sm dark:text-gray-300">Time Blocks</h3>
          <button onclick="addTemplateTimeBlock('${type}')" class="text-xs px-2 py-1 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 rounded hover:bg-blue-200">
            <i class="fas fa-plus mr-1"></i>Add Block
          </button>
        </div>
        <div id="template-time-blocks" class="space-y-2 max-h-64 overflow-y-auto">
          ${(template.timeBlocks || []).map((block, idx) => `
            <div class="flex items-center gap-2 p-2 bg-slate-50 dark:bg-gray-700 rounded-lg" data-block-idx="${idx}">
              <input type="time" value="${convertTo24Hour(block.time)}"
                class="time-input px-2 py-1 border dark:border-gray-600 rounded text-sm dark:bg-gray-600 dark:text-white w-24" />
              <input type="text" value="${escapeHtml(block.title)}"
                class="title-input flex-1 px-2 py-1 border dark:border-gray-600 rounded text-sm dark:bg-gray-600 dark:text-white" />
              <input type="number" value="${block.duration || 60}" min="15" step="15"
                class="duration-input px-2 py-1 border dark:border-gray-600 rounded text-sm dark:bg-gray-600 dark:text-white w-16" placeholder="min" />
              <button onclick="removeTemplateTimeBlock(${idx}, '${type}')" class="text-red-500 hover:text-red-700 px-2">
                <i class="fas fa-times"></i>
              </button>
            </div>
          `).join('')}
        </div>
      </div>

      <!-- Actions -->
      <div class="flex gap-3 pt-4 border-t dark:border-gray-700">
        <button onclick="saveDayTypeTemplate('${type}')" class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          <i class="fas fa-save mr-2"></i>Save Template
        </button>
        <button onclick="resetDayTypeTemplate('${type}')" class="px-4 py-2 border dark:border-gray-600 dark:text-gray-300 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700">
          <i class="fas fa-undo mr-2"></i>Reset to Default
        </button>
        <button onclick="UI.closeModal()" class="px-4 py-2 text-slate-500 dark:text-gray-400 hover:text-slate-700">
          Cancel
        </button>
      </div>
    </div>
  `;

  UI.showModal(content);
}

function convertTo24Hour(timeStr) {
  // Convert "6:00 AM" to "06:00" for input[type=time]
  if (!timeStr) return '09:00';
  const match = timeStr.match(/(\d{1,2}):(\d{2})\s*(AM|PM)?/i);
  if (!match) return '09:00';

  let hours = parseInt(match[1]);
  const minutes = match[2];
  const period = match[3]?.toUpperCase();

  if (period === 'PM' && hours < 12) hours += 12;
  if (period === 'AM' && hours === 12) hours = 0;

  return `${hours.toString().padStart(2, '0')}:${minutes}`;
}

function convertTo12Hour(time24) {
  // Convert "06:00" to "6:00 AM"
  const [hours, minutes] = time24.split(':').map(Number);
  const period = hours >= 12 ? 'PM' : 'AM';
  const hours12 = hours % 12 || 12;
  return `${hours12}:${minutes.toString().padStart(2, '0')} ${period}`;
}

function addTemplateTimeBlock(type) {
  const container = document.getElementById('template-time-blocks');
  const idx = container.children.length;
  const blockHtml = `
    <div class="flex items-center gap-2 p-2 bg-slate-50 dark:bg-gray-700 rounded-lg" data-block-idx="${idx}">
      <input type="time" value="09:00"
        class="time-input px-2 py-1 border dark:border-gray-600 rounded text-sm dark:bg-gray-600 dark:text-white w-24" />
      <input type="text" value="New Block"
        class="title-input flex-1 px-2 py-1 border dark:border-gray-600 rounded text-sm dark:bg-gray-600 dark:text-white" />
      <input type="number" value="60" min="15" step="15"
        class="duration-input px-2 py-1 border dark:border-gray-600 rounded text-sm dark:bg-gray-600 dark:text-white w-16" placeholder="min" />
      <button onclick="removeTemplateTimeBlock(${idx}, '${type}')" class="text-red-500 hover:text-red-700 px-2">
        <i class="fas fa-times"></i>
      </button>
    </div>
  `;
  container.insertAdjacentHTML('beforeend', blockHtml);
}

function removeTemplateTimeBlock(idx, type) {
  const container = document.getElementById('template-time-blocks');
  const block = container.querySelector(`[data-block-idx="${idx}"]`);
  if (block) block.remove();
  // Re-index remaining blocks
  Array.from(container.children).forEach((el, i) => {
    el.setAttribute('data-block-idx', i);
    const btn = el.querySelector('button');
    btn.onclick = () => removeTemplateTimeBlock(i, type);
  });
}

function saveDayTypeTemplate(type) {
  const name = document.getElementById('template-name').value;
  const description = document.getElementById('template-description').value;
  const baseline = document.getElementById('template-baseline').value;
  const stretch = document.getElementById('template-stretch').value;

  // Get selected routines
  const routineCheckboxes = document.querySelectorAll('#template-routines input[type="checkbox"]:checked');
  const routines = Array.from(routineCheckboxes).map(cb => cb.value);

  // Get time blocks
  const blockElements = document.querySelectorAll('#template-time-blocks > div');
  const timeBlocks = Array.from(blockElements).map(el => {
    const timeInput = el.querySelector('.time-input');
    const titleInput = el.querySelector('.title-input');
    const durationInput = el.querySelector('.duration-input');
    return {
      time: convertTo12Hour(timeInput.value),
      title: titleInput.value,
      duration: parseInt(durationInput.value) || 60
    };
  }).sort((a, b) => {
    // Sort by time
    return convertTo24Hour(a.time).localeCompare(convertTo24Hour(b.time));
  });

  // Update template
  if (!state.DayTypeTemplates) state.DayTypeTemplates = {};
  state.DayTypeTemplates[type] = {
    name,
    description,
    timeBlocks,
    routines,
    goals: { baseline, stretch }
  };

  stateManager.update({ DayTypeTemplates: state.DayTypeTemplates });
  Helpers.logActivity('template_updated', `Updated ${type}-Day template`, { type, name });

  UI.closeModal();
  UI.showToast('Template Saved', `${name} template updated`, 'success');
  render();
}

function resetDayTypeTemplate(type) {
  if (!confirm(`Reset ${type}-Day template to default? This cannot be undone.`)) return;

  const defaults = {
    A: {
      name: 'Optimal Day',
      description: 'Full energy, maximum output',
      timeBlocks: [
        { time: '6:00 AM', title: 'Morning Routine', duration: 60 },
        { time: '7:00 AM', title: 'Commute / Prep', duration: 30 },
        { time: '7:30 AM', title: 'Deep Work Block 1', duration: 90 },
        { time: '9:00 AM', title: 'Break / Recharge', duration: 15 },
        { time: '9:15 AM', title: 'Deep Work Block 2', duration: 90 },
        { time: '10:45 AM', title: 'Admin / Email', duration: 45 },
        { time: '11:30 AM', title: 'Deep Work Block 3', duration: 90 },
        { time: '1:00 PM', title: 'Lunch Break', duration: 60 },
        { time: '2:00 PM', title: 'Deep Work Block 4', duration: 90 },
        { time: '3:30 PM', title: 'Meetings / Collaboration', duration: 90 },
        { time: '5:00 PM', title: 'Wrap-up / Plan Tomorrow', duration: 30 },
        { time: '5:30 PM', title: 'Evening Routine', duration: 90 }
      ],
      routines: ['Morning', 'Commute', 'Evening'],
      goals: { baseline: 'Complete 4 deep work blocks', stretch: 'Clear inbox + bonus task' }
    },
    B: {
      name: 'Low Energy Day',
      description: 'Conserve energy, focus on essentials',
      timeBlocks: [
        { time: '7:00 AM', title: 'Gentle Morning Routine', duration: 60 },
        { time: '8:00 AM', title: 'Light Admin Tasks', duration: 60 },
        { time: '9:00 AM', title: 'Focus Block 1', duration: 60 },
        { time: '10:00 AM', title: 'Break / Movement', duration: 30 },
        { time: '10:30 AM', title: 'Focus Block 2', duration: 60 },
        { time: '11:30 AM', title: 'Email / Communication', duration: 30 },
        { time: '12:00 PM', title: 'Lunch + Rest', duration: 90 },
        { time: '1:30 PM', title: 'Focus Block 3', duration: 60 },
        { time: '2:30 PM', title: 'Light Tasks / Review', duration: 90 },
        { time: '4:00 PM', title: 'Wrap-up', duration: 30 },
        { time: '4:30 PM', title: 'Evening Routine', duration: 60 }
      ],
      routines: ['Morning', 'Evening'],
      goals: { baseline: 'Complete 3 focus blocks', stretch: 'One bonus task if energy allows' }
    },
    C: {
      name: 'Chaos Day',
      description: 'Survival mode - one priority only',
      timeBlocks: [
        { time: '7:00 AM', title: 'Basic Morning', duration: 30 },
        { time: '7:30 AM', title: 'Identify ONE Priority', duration: 15 },
        { time: '7:45 AM', title: 'Work on Priority', duration: 120 },
        { time: '9:45 AM', title: 'Break', duration: 15 },
        { time: '10:00 AM', title: 'Continue Priority', duration: 120 },
        { time: '12:00 PM', title: 'Lunch', duration: 60 },
        { time: '1:00 PM', title: 'Priority Push', duration: 120 },
        { time: '3:00 PM', title: 'Essential Only', duration: 120 },
        { time: '5:00 PM', title: 'Minimal Evening Routine', duration: 30 }
      ],
      routines: ['Evening'],
      goals: { baseline: 'Complete ONE priority task', stretch: 'Survive and reset for tomorrow' }
    }
  };

  state.DayTypeTemplates[type] = defaults[type];
  stateManager.update({ DayTypeTemplates: state.DayTypeTemplates });

  UI.closeModal();
  UI.showToast('Template Reset', `${type}-Day template restored to default`, 'success');
  openDayTypeTemplateEditor(type); // Reopen with fresh data
}

function addTimeBlock() {
  const todayPlan = Helpers.getDayPlan();
  const newBlock = {
    id: stateManager.generateId(),
    time: '09:00',
    title: 'New Time Block',
    completed: false
  };
  todayPlan.time_blocks.push(newBlock);
  state.DayPlans[todayPlan.date] = todayPlan;
  stateManager.update({ DayPlans: state.DayPlans });
  render();
}

function updateTimeBlock(id, field, value) {
  const todayPlan = Helpers.getDayPlan();
  const block = todayPlan.time_blocks.find(b => b.id === id);
  if (block) {
    block[field] = value;
    state.DayPlans[todayPlan.date] = todayPlan;
    stateManager.update({ DayPlans: state.DayPlans });
  }
}

function removeTimeBlock(id) {
  const todayPlan = Helpers.getDayPlan();
  todayPlan.time_blocks = todayPlan.time_blocks.filter(b => b.id !== id);
  state.DayPlans[todayPlan.date] = todayPlan;
  stateManager.update({ DayPlans: state.DayPlans });
  render();
}

function toggleTimeBlockCompletion(id) {
  const todayPlan = Helpers.getDayPlan();
  const block = todayPlan.time_blocks.find(b => b.id === id);
  if (block) {
    block.completed = !block.completed;
    if (block.completed) {
      Helpers.logActivity('time_block_completed', `Completed time block: ${block.title}`, { blockId: block.id });
    }
    state.DayPlans[todayPlan.date] = todayPlan;
    stateManager.update({ DayPlans: state.DayPlans });
    Helpers.saveProgressSnapshot();
    render();
  }
}

function saveGoals() {
  const todayPlan = Helpers.getDayPlan();
  const baseline = document.getElementById('baseline-goal')?.value || todayPlan.baseline_goal.text;
  const stretch = document.getElementById('stretch-goal')?.value || todayPlan.stretch_goal.text;
  
  todayPlan.baseline_goal.text = baseline;
  todayPlan.stretch_goal.text = stretch;
  state.DayPlans[todayPlan.date] = todayPlan;
  stateManager.update({ DayPlans: state.DayPlans });
  UI.showToast('Goals Saved', 'Your daily goals have been updated', 'success');
}

function toggleGoalCompletion(type) {
  const todayPlan = Helpers.getDayPlan();
  todayPlan[`${type}_goal`].completed = !todayPlan[`${type}_goal`].completed;
  if (todayPlan[`${type}_goal`].completed) {
    const goalType = type === 'baseline' ? 'Baseline' : 'Stretch';
    Helpers.logActivity('goal_achieved', `Achieved ${goalType} Goal: ${todayPlan[`${type}_goal`].text}`, { goalType: type });
  }
  state.DayPlans[todayPlan.date] = todayPlan;
  stateManager.update({ DayPlans: state.DayPlans });
  Helpers.saveProgressSnapshot();
  render();
}

function openCreateModal() {
  const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
  const usedLetters = state.AZTask.map(t => t.letter);
  const availableLetters = letters.filter(l => !usedLetters.includes(l));
  
  const content = `
    <div class="p-6">
      <h2 class="text-xl font-bold mb-4 dark:text-white">Create A–Z Task</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-1 dark:text-gray-300">Letter</label>
          <select id="modal-letter" class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2">
            ${availableLetters.map(l => `<option value="${l}">${l}</option>`).join('')}
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium mb-1 dark:text-gray-300">Task Description</label>
          <input
            id="modal-task"
            type="text"
            placeholder="What needs to be done?"
            class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2"
          />
        </div>
        <div>
          <label class="block text-sm font-medium mb-1 dark:text-gray-300">Notes (Optional)</label>
          <textarea
            id="modal-notes"
            placeholder="Additional details..."
            class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2"
            rows="3"
          ></textarea>
        </div>
      </div>
      <div class="flex justify-end gap-3 mt-6">
        <button onclick="UI.closeModal()" class="px-4 py-2 border dark:border-gray-600 dark:text-gray-300 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700">
          Cancel
        </button>
        <button onclick="createTask()" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          Create Task
        </button>
      </div>
    </div>
  `;
  
  UI.showModal(content);
}

function openEditModal(id) {
  const task = state.AZTask.find(t => t.id === id);
  if (!task) return;
  
  const content = `
    <div class="p-6">
      <h2 class="text-xl font-bold mb-4 dark:text-white">Edit Task ${task.letter}</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-1 dark:text-gray-300">Task Description</label>
          <input
            id="edit-task"
            type="text"
            value="${UI.sanitize(task.task)}"
            class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2"
          />
        </div>
        <div>
          <label class="block text-sm font-medium mb-1 dark:text-gray-300">Notes</label>
          <textarea
            id="edit-notes"
            class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2"
            rows="3"
          >${UI.sanitize(task.notes || '')}</textarea>
        </div>
        <div>
          <label class="block text-sm font-medium mb-1 dark:text-gray-300">Status</label>
          <select id="edit-status" class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2">
            <option value="Not Started" ${task.status === 'Not Started' ? 'selected' : ''}>Not Started</option>
            <option value="In Progress" ${task.status === 'In Progress' ? 'selected' : ''}>In Progress</option>
            <option value="Completed" ${task.status === 'Completed' ? 'selected' : ''}>Completed</option>
          </select>
        </div>
      </div>
      <div class="flex justify-end gap-3 mt-6">
        <button onclick="UI.closeModal()" class="px-4 py-2 border dark:border-gray-600 dark:text-gray-300 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700">
          Cancel
        </button>
        <button onclick="updateTask('${task.id}')" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          Update Task
        </button>
      </div>
    </div>
  `;
  
  UI.showModal(content);
}

function createTask() {
  const letter = document.getElementById('modal-letter').value;
  const task = document.getElementById('modal-task').value;
  const notes = document.getElementById('modal-notes').value;

  const newTask = {
    id: stateManager.generateId(),
    letter,
    task: task.trim(),
    notes: notes.trim(),
    status: 'Not Started',
    createdAt: new Date().toISOString()
  };

  // Validate task data
  const validationErrors = DataValidator.validateTask(newTask);
  if (validationErrors.length > 0) {
    UI.showToast('Validation Error', validationErrors[0], 'error');
    return;
  }

  state.AZTask.push(newTask);
  state.AZTask.sort((a, b) => a.letter.localeCompare(b.letter));
  Helpers.logActivity('task_created', `Created A-Z Task: ${letter} - ${task.trim()}`, { taskId: newTask.id });
  stateManager.update({ AZTask: state.AZTask });
  UI.closeModal();
  render();
  UI.showToast('Task Created', `${letter} – ${task}`, 'success');
}

function updateTask(id) {
  const task = state.AZTask.find(t => t.id === id);
  if (!task) return;

  const oldStatus = task.status;
  task.task = document.getElementById('edit-task').value.trim();
  task.notes = document.getElementById('edit-notes').value.trim();
  task.status = document.getElementById('edit-status').value;

  // Validate updated task data
  const validationErrors = DataValidator.validateTask(task);
  if (validationErrors.length > 0) {
    UI.showToast('Validation Error', validationErrors[0], 'error');
    return;
  }

  if (oldStatus !== task.status && task.status === 'Completed') {
    Helpers.logActivity('task_completed', `Completed A-Z Task: ${task.letter} - ${task.task}`, { taskId: task.id });
  } else if (oldStatus !== task.status) {
    Helpers.logActivity('task_updated', `Updated A-Z Task: ${task.letter} - ${task.task} (${task.status})`, { taskId: task.id });
  }

  stateManager.update({ AZTask: state.AZTask });
  UI.closeModal();
  render();
  UI.showToast('Task Updated', `${task.letter} – ${task.task}`, 'success');
}

function exportState() {
  const dataStr = JSON.stringify(state, null, 2);
  const dataBlob = new Blob([dataStr], { type: 'application/json' });
  const url = URL.createObjectURL(dataBlob);

  const link = document.createElement('a');
  link.href = url;
  link.download = `cycleboard-backup-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  // Track export statistics
  localStorage.setItem('cycleboard-last-export', new Date().toISOString());
  const exportCount = parseInt(localStorage.getItem('cycleboard-export-count') || '0');
  localStorage.setItem('cycleboard-export-count', (exportCount + 1).toString());

  const dataSize = (JSON.stringify(state).length / 1024).toFixed(1);
  UI.showToast('Export Successful', `Data backed up (${dataSize} KB)`, 'success');
}

function showImportModal() {
  const content = `
    <div class="p-6">
      <h2 class="text-xl font-bold mb-4 dark:text-white">Import Data</h2>
      <p class="text-slate-600 dark:text-gray-300 mb-6">
        Import a previously exported JSON file. This will replace your current data.
      </p>
      <div class="border-2 border-dashed border-slate-300 dark:border-gray-600 rounded-lg p-8 text-center">
        <i class="fas fa-file-import text-4xl text-slate-400 dark:text-gray-500 mb-4"></i>
        <p class="text-slate-600 dark:text-gray-300 mb-4">Drag and drop your JSON file here, or click to browse</p>
        <input
          type="file"
          id="import-file"
          accept=".json"
          class="hidden"
          onchange="handleFileImport(event)"
        />
        <label for="import-file" class="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 cursor-pointer">
          Browse Files
        </label>
      </div>
      <div class="flex justify-end mt-6">
        <button onclick="UI.closeModal()" class="px-4 py-2 border dark:border-gray-600 dark:text-gray-300 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700">
          Cancel
        </button>
      </div>
    </div>
  `;
  
  UI.showModal(content);
}

function handleFileImport(event) {
  const file = event.target.files[0];
  if (!file) return;

  UI.showLoading('Reading file...');

  const reader = new FileReader();
  reader.onload = function(e) {
    try {
      UI.showLoading('Validating data...');
      const imported = JSON.parse(e.target.result);

      // Validate imported data
      const validationErrors = DataValidator.validateImportData(imported);
      if (validationErrors.length > 0) {
        UI.hideLoading();
        UI.showToast('Validation Error', validationErrors[0], 'error');
        return;
      }

      // Migrate data to fill in missing features from older backups
      UI.showLoading('Migrating data...');
      const defaultState = stateManager.getDefaultState();
      const { migrated, migratedFeatures } = DataValidator.migrateImportData(imported, defaultState);

      UI.hideLoading();

      // Build confirmation message
      let confirmMsg = 'This will replace all your current data.';
      if (migratedFeatures.length > 0) {
        confirmMsg += `\n\nNote: ${migratedFeatures.length} missing feature(s) will be initialized with defaults:\n• ${migratedFeatures.join('\n• ')}`;
      }
      confirmMsg += '\n\nContinue?';

      if (confirm(confirmMsg)) {
        UI.showLoading('Importing data...');

        // Reset state and apply migrated data
        Object.keys(state).forEach(key => delete state[key]);
        Object.assign(state, migrated);
        stateManager.update(state);

        // Track import statistics
        localStorage.setItem('cycleboard-last-import', new Date().toISOString());

        UI.closeModal();
        UI.hideLoading();
        render();

        const dataSize = (JSON.stringify(migrated).length / 1024).toFixed(1);
        let successMsg = `Data restored (${dataSize} KB)`;
        if (migratedFeatures.length > 0) {
          successMsg += ` - ${migratedFeatures.length} feature(s) migrated`;
        }
        UI.showToast('Import Successful', successMsg, 'success');
      }
    } catch (err) {
      UI.hideLoading();
      console.error('Import error:', err);
      UI.showToast('Import Failed', 'The file is not a valid CycleBoard backup', 'error');
    }
  };

  reader.onerror = function() {
    UI.hideLoading();
    UI.showToast('Import Failed', 'Could not read the file', 'error');
  };

  reader.readAsText(file);
}

function clearData() {
  if (confirm('Are you sure you want to delete ALL data? This cannot be undone.')) {
    localStorage.removeItem('cycleboard-state');
    // Clear current state and replace with defaults
    const defaultState = stateManager.getDefaultState();
    Object.keys(stateManager.state).forEach(key => delete stateManager.state[key]);
    Object.assign(stateManager.state, defaultState);
    stateManager.saveToStorage();
    render();
    UI.showToast('Data Cleared', 'All data has been deleted', 'warning');
  }
}

function resetToDefaults() {
  if (confirm('Reset all settings to defaults?')) {
    state.Settings = stateManager.getDefaultState().Settings;
    stateManager.update({ Settings: state.Settings });
    render();
    UI.showToast('Settings Reset', 'All settings restored to defaults', 'success');
  }
}

function toggleSetting(setting) {
  state.Settings[setting] = !state.Settings[setting];
  stateManager.update({ Settings: state.Settings });
  render();
}

function updateSetting(setting, value) {
  state.Settings[setting] = value;
  stateManager.update({ Settings: state.Settings });
}

function toggleDarkMode() {
  state.Settings.darkMode = !state.Settings.darkMode;
  stateManager.update({ Settings: state.Settings });
  
  if (state.Settings.darkMode) {
    document.documentElement.classList.add('dark');
    document.body.classList.add('bg-gray-900', 'text-white');
    document.body.classList.remove('bg-slate-50');
  } else {
    document.documentElement.classList.remove('dark');
    document.body.classList.remove('bg-gray-900', 'text-white');
    document.body.classList.add('bg-slate-50');
  }
  
  render();
}

// Routine Management Functions
function addNewRoutineType() {
  const content = `
    <div class="p-6">
      <h2 class="text-xl font-bold mb-4 dark:text-white">Create New Routine</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-1 dark:text-gray-300">Routine Name</label>
          <input
            id="new-routine-name"
            type="text"
            class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2"
            placeholder="e.g., Workout, Afternoon, Work"
          />
        </div>
        <div class="text-sm text-slate-500 dark:text-gray-400">
          <p class="mb-2">Suggested routines:</p>
          <div class="flex flex-wrap gap-2">
            <button onclick="document.getElementById('new-routine-name').value='Workout'; document.getElementById('new-routine-name').focus();"
                    class="px-3 py-1 bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300 rounded-full text-xs hover:bg-green-200 dark:hover:bg-green-900/50">
              Workout
            </button>
            <button onclick="document.getElementById('new-routine-name').value='Afternoon'; document.getElementById('new-routine-name').focus();"
                    class="px-3 py-1 bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300 rounded-full text-xs hover:bg-orange-200 dark:hover:bg-orange-900/50">
              Afternoon
            </button>
            <button onclick="document.getElementById('new-routine-name').value='Work'; document.getElementById('new-routine-name').focus();"
                    class="px-3 py-1 bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300 rounded-full text-xs hover:bg-indigo-200 dark:hover:bg-indigo-900/50">
              Work
            </button>
            <button onclick="document.getElementById('new-routine-name').value='Bedtime'; document.getElementById('new-routine-name').focus();"
                    class="px-3 py-1 bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300 rounded-full text-xs hover:bg-purple-200 dark:hover:bg-purple-900/50">
              Bedtime
            </button>
          </div>
        </div>
      </div>
      <div class="flex gap-3 mt-6">
        <button onclick="createNewRoutine()" class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          Create Routine
        </button>
        <button onclick="UI.closeModal()" class="flex-1 px-4 py-2 bg-slate-200 dark:bg-gray-700 dark:text-white rounded-lg hover:bg-slate-300 dark:hover:bg-gray-600">
          Cancel
        </button>
      </div>
    </div>
  `;
  UI.showModal(content);
  setTimeout(() => document.getElementById('new-routine-name').focus(), 100);
}

function createNewRoutine() {
  const name = document.getElementById('new-routine-name').value.trim();
  if (!name) {
    UI.showToast('Error', 'Please enter a routine name', 'error');
    return;
  }

  if (state.Routine[name]) {
    UI.showToast('Error', 'A routine with this name already exists', 'error');
    return;
  }

  state.Routine[name] = [];
  stateManager.update({ Routine: state.Routine });
  UI.closeModal();
  render();
  UI.showToast('Routine Created', `${name} routine has been created`, 'success');
  Helpers.logActivity('routine_created', `Created new routine: ${name}`);
}

function deleteRoutineType(routineName) {
  if (!confirm(`Delete "${routineName}" routine and all its steps?`)) return;

  delete state.Routine[routineName];
  stateManager.update({ Routine: state.Routine });
  render();
  UI.showToast('Routine Deleted', `${routineName} routine has been deleted`, 'warning');
  Helpers.logActivity('routine_deleted', `Deleted routine: ${routineName}`);
}

function addRoutineStep(routineName) {
  if (!state.Routine[routineName]) return;

  state.Routine[routineName].push('New step');
  stateManager.update({ Routine: state.Routine });
  render();

  // Focus on the new input
  setTimeout(() => {
    const inputs = document.querySelectorAll(`input[type="text"]`);
    if (inputs.length > 0) {
      const lastInput = inputs[inputs.length - 1];
      lastInput.focus();
      lastInput.select();
    }
  }, 100);
}

function updateRoutineStep(routineName, index, value) {
  if (!state.Routine[routineName]) return;

  const trimmedValue = value.trim();

  // Validate routine step
  const validationErrors = DataValidator.validateRoutineStep(trimmedValue);
  if (validationErrors.length > 0) {
    UI.showToast('Validation Error', validationErrors[0], 'error');
    render(); // Reset to previous value
    return;
  }

  state.Routine[routineName][index] = trimmedValue;
  stateManager.update({ Routine: state.Routine });
  Helpers.logActivity('routine_step_updated', `Updated step in ${routineName} routine`);
}

function deleteRoutineStep(routineName, index) {
  if (!state.Routine[routineName]) return;

  state.Routine[routineName].splice(index, 1);
  stateManager.update({ Routine: state.Routine });
  render();
  UI.showToast('Step Deleted', 'Routine step removed', 'info');
  Helpers.logActivity('routine_step_deleted', `Deleted step from ${routineName} routine`);
}

function moveRoutineStep(routineName, index, direction) {
  if (!state.Routine[routineName]) return;

  const routine = state.Routine[routineName];
  const newIndex = direction === 'up' ? index - 1 : index + 1;

  if (newIndex < 0 || newIndex >= routine.length) return;

  // Swap items
  [routine[index], routine[newIndex]] = [routine[newIndex], routine[index]];

  stateManager.update({ Routine: state.Routine });
  render();
}

function toggleRoutineStep(routineName, stepIndex, completed) {
  const todayPlan = Helpers.getDayPlan();
  if (!todayPlan.routines_completed) todayPlan.routines_completed = {};
  if (!todayPlan.routines_completed[routineName]) {
    todayPlan.routines_completed[routineName] = { completed: false, steps: {} };
  }

  todayPlan.routines_completed[routineName].steps[stepIndex] = completed;

  // Auto-complete routine if all steps are done
  const routine = state.Routine[routineName];
  const completedSteps = Object.values(todayPlan.routines_completed[routineName].steps).filter(Boolean).length;
  if (completedSteps === routine.length) {
    todayPlan.routines_completed[routineName].completed = true;
    UI.showToast('Routine Complete!', `${routineName} routine finished 🎉`, 'success');
    Helpers.logActivity('routine_completed', `Completed ${routineName} routine`, { routine: routineName });
  } else {
    todayPlan.routines_completed[routineName].completed = false;
  }

  state.DayPlans[todayPlan.date] = todayPlan;
  stateManager.update({ DayPlans: state.DayPlans });
  render();
}

function toggleRoutineComplete(routineName) {
  const todayPlan = Helpers.getDayPlan();
  if (!todayPlan.routines_completed) todayPlan.routines_completed = {};
  if (!todayPlan.routines_completed[routineName]) {
    todayPlan.routines_completed[routineName] = { completed: false, steps: {} };
  }

  const newCompleteState = !todayPlan.routines_completed[routineName].completed;
  todayPlan.routines_completed[routineName].completed = newCompleteState;

  // Mark all steps as completed/uncompleted
  const routine = state.Routine[routineName];
  routine.forEach((step, index) => {
    todayPlan.routines_completed[routineName].steps[index] = newCompleteState;
  });

  state.DayPlans[todayPlan.date] = todayPlan;
  stateManager.update({ DayPlans: state.DayPlans });
  Helpers.saveProgressSnapshot();
  render();

  if (newCompleteState) {
    UI.showToast('Routine Complete!', `${routineName} routine marked as done 🎉`, 'success');
    Helpers.logActivity('routine_completed', `Completed ${routineName} routine`, { routine: routineName });
  } else {
    UI.showToast('Routine Unchecked', `${routineName} routine marked as incomplete`, 'info');
  }
}

// Journal Management Functions
function openJournalModal(entryId = null, entryType = 'free') {
  const entry = entryId ? state.Journal.find(e => e.id === entryId) : null;
  const isEdit = !!entry;
  const type = entry ? (entry.entryType || 'free') : entryType;

  const content = `
    <div class="p-6 max-h-[85vh] overflow-y-auto">
      <h2 class="text-2xl font-bold mb-6 dark:text-white">${isEdit ? 'Edit' : 'New'} Journal Entry</h2>

      <div class="space-y-4">
        <!-- Entry Type Selector -->
        <div>
          <label class="block text-sm font-medium text-slate-700 dark:text-gray-300 mb-2">Entry Type</label>
          <div class="grid grid-cols-3 gap-2">
            <button type="button" onclick="switchJournalType('free', '${entryId || ''}')"
                    class="p-3 rounded-lg border-2 transition-all ${type === 'free' ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-200 dark:border-gray-600'}">
              <i class="fas fa-pen text-blue-500 mb-1"></i>
              <p class="text-xs font-medium dark:text-gray-300">Free Entry</p>
            </button>
            <button type="button" onclick="switchJournalType('weekly', '${entryId || ''}')"
                    class="p-3 rounded-lg border-2 transition-all ${type === 'weekly' ? 'border-green-500 bg-green-50 dark:bg-green-900/20' : 'border-gray-200 dark:border-gray-600'}">
              <i class="fas fa-calendar-week text-green-500 mb-1"></i>
              <p class="text-xs font-medium dark:text-gray-300">Weekly Review</p>
            </button>
            <button type="button" onclick="switchJournalType('gratitude', '${entryId || ''}')"
                    class="p-3 rounded-lg border-2 transition-all ${type === 'gratitude' ? 'border-amber-500 bg-amber-50 dark:bg-amber-900/20' : 'border-gray-200 dark:border-gray-600'}">
              <i class="fas fa-heart text-amber-500 mb-1"></i>
              <p class="text-xs font-medium dark:text-gray-300">Gratitude</p>
            </button>
          </div>
        </div>

        <input type="hidden" id="journal-entry-type" value="${type}" />

        <div>
          <label class="block text-sm font-medium text-slate-700 dark:text-gray-300 mb-2">Title</label>
          <input
            type="text"
            id="journal-title"
            value="${entry ? UI.sanitize(entry.title) : ''}"
            placeholder="Entry title..."
            class="w-full px-4 py-2 border dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-700 dark:text-gray-300 mb-2">Content</label>
          <textarea
            id="journal-content"
            rows="8"
            placeholder="Write your thoughts..."
            class="w-full px-4 py-2 border dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white"
          >${entry ? UI.sanitize(entry.content) : ''}</textarea>
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-700 dark:text-gray-300 mb-2">Tags (comma-separated)</label>
          <input
            type="text"
            id="journal-tags"
            value="${entry && entry.tags ? entry.tags.join(', ') : ''}"
            placeholder="work, personal, reflection..."
            class="w-full px-4 py-2 border dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-700 dark:text-gray-300 mb-2">Mood (optional emoji)</label>
          <select
            id="journal-mood"
            class="w-full px-4 py-2 border dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white"
          >
            <option value="">No mood</option>
            <option value="ðŸ˜Š" ${entry && entry.mood === 'ðŸ˜Š' ? 'selected' : ''}>ðŸ˜Š Happy</option>
            <option value="ðŸ˜Œ" ${entry && entry.mood === 'ðŸ˜Œ' ? 'selected' : ''}>ðŸ˜Œ Peaceful</option>
            <option value="ðŸ¤”" ${entry && entry.mood === 'ðŸ¤”' ? 'selected' : ''}>ðŸ¤” Thoughtful</option>
            <option value="ðŸ’ª" ${entry && entry.mood === 'ðŸ’ª' ? 'selected' : ''}>ðŸ’ª Motivated</option>
            <option value="ðŸ˜“" ${entry && entry.mood === 'ðŸ˜“' ? 'selected' : ''}>ðŸ˜“ Tired</option>
            <option value="ðŸ˜”" ${entry && entry.mood === 'ðŸ˜”' ? 'selected' : ''}>ðŸ˜” Down</option>
            <option value="ðŸŽ‰" ${entry && entry.mood === 'ðŸŽ‰' ? 'selected' : ''}>ðŸŽ‰ Excited</option>
            <option value="ðŸ˜¤" ${entry && entry.mood === 'ðŸ˜¤' ? 'selected' : ''}>ðŸ˜¤ Determined</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-700 dark:text-gray-300 mb-2">Link to A-Z Tasks (optional)</label>
          <select
            id="journal-tasks"
            multiple
            class="w-full px-4 py-2 border dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white"
            style="height: 120px"
          >
            ${state.AZTask.map(task => `
              <option value="${task.id}" ${entry && entry.linkedTasks && entry.linkedTasks.includes(task.id) ? 'selected' : ''}>
                ${task.letter}: ${UI.sanitize(task.task)}
              </option>
            `).join('')}
          </select>
          <p class="text-xs text-slate-500 dark:text-gray-400 mt-1">Hold Ctrl/Cmd to select multiple</p>
        </div>
      </div>

      <div class="flex gap-3 mt-6">
        <button
          onclick="saveJournalEntry('${entryId || ''}')"
          class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          ${isEdit ? 'Update' : 'Create'} Entry
        </button>
        <button
          onclick="UI.closeModal()"
          class="px-4 py-2 border dark:border-gray-600 dark:text-gray-300 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700"
        >
          Cancel
        </button>
      </div>
    </div>
  `;

  UI.showModal(content);
}

function saveJournalEntry(entryId) {
  const title = document.getElementById('journal-title').value.trim();
  const content = document.getElementById('journal-content').value.trim();
  const tagsInput = document.getElementById('journal-tags').value.trim();
  const mood = document.getElementById('journal-mood').value;
  const taskSelect = document.getElementById('journal-tasks');
  const linkedTasks = Array.from(taskSelect.selectedOptions).map(opt => opt.value);
  const entryType = document.getElementById('journal-entry-type')?.value || 'free';

  if (!title) {
    UI.showToast('Validation Error', 'Please enter a title', 'error');
    return;
  }

  if (!content) {
    UI.showToast('Validation Error', 'Please enter some content', 'error');
    return;
  }

  if (title.length > 200) {
    UI.showToast('Validation Error', 'Title too long (max 200 characters)', 'error');
    return;
  }

  if (content.length > 5000) {
    UI.showToast('Validation Error', 'Content too long (max 5000 characters)', 'error');
    return;
  }

  const tags = tagsInput ? tagsInput.split(',').map(t => t.trim()).filter(t => t) : [];

  if (entryId) {
    // Update existing entry
    const entryIndex = state.Journal.findIndex(e => e.id === entryId);
    if (entryIndex !== -1) {
      state.Journal[entryIndex] = {
        ...state.Journal[entryIndex],
        title,
        content,
        tags,
        mood,
        linkedTasks,
        entryType,
        updatedAt: new Date().toISOString()
      };
      Helpers.logActivity('journal_updated', `Updated journal entry: ${title}`, { entryId });
      UI.showToast('Entry Updated', 'Journal entry has been updated', 'success');
    }
  } else {
    // Create new entry
    const newEntry = {
      id: 'j' + Date.now(),
      title,
      content,
      tags,
      mood,
      linkedTasks,
      entryType,
      timestamp: new Date().toISOString(),
      createdAt: new Date().toISOString()
    };
    state.Journal.push(newEntry);
    Helpers.logActivity('journal_created', `Created journal entry: ${title}`, { entryId: newEntry.id });
    UI.showToast('Entry Created', 'New journal entry has been saved', 'success');
  }

  stateManager.update({ Journal: state.Journal });
  UI.closeModal();
  render();
}

function editJournalEntry(entryId) {
  openJournalModal(entryId);
}

function deleteJournalEntry(entryId) {
  const entry = state.Journal.find(e => e.id === entryId);
  if (!entry) return;

  if (confirm(`Delete journal entry "${entry.title}"?`)) {
    state.Journal = state.Journal.filter(e => e.id !== entryId);
    stateManager.update({ Journal: state.Journal });
    Helpers.logActivity('journal_deleted', `Deleted journal entry: ${entry.title}`, { entryId });
    UI.showToast('Entry Deleted', 'Journal entry has been removed', 'success');
    render();
  }
}

function sortTasks() {
  state.AZTask.sort((a, b) => a.letter.localeCompare(b.letter));
  stateManager.update({ AZTask: state.AZTask });
  render();
  UI.showToast('Tasks Sorted', 'A-Z tasks sorted alphabetically', 'info');
}

function filterTasks(status) {
  setAzFilter(status);
  render();
}

// Internal function that performs the actual search
function _performSearch(query) {
  setAzSearch(query);
  render();
}

// Debounced search - waits 300ms after user stops typing
const debouncedSearch = debounce(_performSearch, 300);

function searchTasks(query) {
  // Update state immediately for responsiveness
  setAzSearch(query);
  // Debounce the expensive render operation
  debouncedSearch(query);
}

function completeAllTodayTasks() {
  state.AZTask.forEach(task => {
    if (task.status !== 'Completed') {
      task.status = 'Completed';
    }
  });
  stateManager.update({ AZTask: state.AZTask });
  render();
  UI.showToast('All Tasks Completed', 'Great job completing all tasks!', 'success');
}

function addFocusTask(areaId) {
  const content = `
    <div class="p-6">
      <h2 class="text-xl font-bold mb-4 dark:text-white">Add Focus Area Task</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-1 dark:text-gray-300">Task Description</label>
          <input
            id="focus-task-text"
            type="text"
            placeholder="What do you want to accomplish?"
            class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2"
          />
        </div>
      </div>
      <div class="flex justify-end gap-3 mt-6">
        <button onclick="UI.closeModal()" class="px-4 py-2 border dark:border-gray-600 dark:text-gray-300 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700">
          Cancel
        </button>
        <button onclick="createFocusTask('${areaId}')" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          Add Task
        </button>
      </div>
    </div>
  `;
  UI.showModal(content);
}

function createFocusTask(areaId) {
  const text = document.getElementById('focus-task-text').value.trim();
  if (!text) {
    UI.showToast('Error', 'Task description is required', 'error');
    return;
  }
  
  const area = state.FocusArea.find(a => a.id === areaId);
  if (!area) return;
  
  if (!area.tasks) area.tasks = [];
  
  area.tasks.push({
    id: stateManager.generateId(),
    text: text,
    completed: false,
    createdAt: new Date().toISOString()
  });
  
  Helpers.logActivity('focus_task_added', `Added task to ${area.name}: ${text}`, { areaId: areaId });
  stateManager.update({ FocusArea: state.FocusArea });
  UI.closeModal();
  render();
  UI.showToast('Task Added', `Added to ${area.name}`, 'success');
}

function toggleFocusTask(areaId, taskId) {
  const area = state.FocusArea.find(a => a.id === areaId);
  if (!area || !area.tasks) return;

  const task = area.tasks.find(t => t.id === taskId);
  if (task) {
    task.completed = !task.completed;
    if (task.completed) {
      Helpers.logActivity('focus_task_completed', `Completed ${area.name} task: ${task.text}`, { areaId: areaId, taskId: taskId });
    }
    stateManager.update({ FocusArea: state.FocusArea });
    Helpers.saveProgressSnapshot();
    render();
  }
}

function removeFocusTask(areaId, taskId) {
  const area = state.FocusArea.find(a => a.id === areaId);
  if (!area || !area.tasks) return;
  
  if (confirm('Delete this task?')) {
    area.tasks = area.tasks.filter(t => t.id !== taskId);
    stateManager.update({ FocusArea: state.FocusArea });
    render();
    UI.showToast('Task Deleted', 'Focus task removed', 'warning');
  }
}

function addManualNote() {
  const content = `
    <div class="p-6">
      <h2 class="text-xl font-bold mb-4 dark:text-white">Add Manual Note</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-1 dark:text-gray-300">What happened?</label>
          <textarea
            id="manual-note-text"
            placeholder="Document anything not automatically captured..."
            class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2"
            rows="5"
          ></textarea>
        </div>
      </div>
      <div class="flex justify-end gap-3 mt-6">
        <button onclick="UI.closeModal()" class="px-4 py-2 border dark:border-gray-600 dark:text-gray-300 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700">
          Cancel
        </button>
        <button onclick="saveManualNote()" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          Save Note
        </button>
      </div>
    </div>
  `;
  UI.showModal(content);
}

function saveManualNote() {
  const text = document.getElementById('manual-note-text').value.trim();
  if (!text) {
    UI.showToast('Error', 'Note text is required', 'error');
    return;
  }

  Helpers.logActivity('manual_note', text, {});
  UI.closeModal();
  render();
  UI.showToast('Note Added', 'Manual note saved to timeline', 'success');
}

// 8 Steps to Success Functions
function toggleEightStep(stepId) {
  const todayDate = stateManager.getTodayDate();
  if (!state.EightSteps[todayDate]) {
    state.EightSteps[todayDate] = {};
  }
  state.EightSteps[todayDate][stepId] = !state.EightSteps[todayDate][stepId];

  const stepNames = {
    positiveAttitude: 'Positive Attitude',
    beOnTime: 'Be on Time',
    bePrepared: 'Be Prepared',
    workFullDay: 'Work Full Day',
    workTerritory: 'Work Territory',
    greatAttitude: 'Great Attitude',
    knowWhy: 'Know Your Why',
    takeControl: 'Take Control'
  };

  if (state.EightSteps[todayDate][stepId]) {
    Helpers.logActivity('eight_step_completed', `Completed step: ${stepNames[stepId]}`, { step: stepId });

    // Check if all 8 steps completed
    const completedCount = Object.values(state.EightSteps[todayDate]).filter(Boolean).length;
    if (completedCount === 8) {
      UI.showToast('All Steps Complete!', 'You\'ve achieved daily excellence!', 'success');
    }
  }

  stateManager.update({ EightSteps: state.EightSteps });
  render();
}

// Contingency Functions
function activateContingency(type) {
  const contingencyInfo = {
    runningLate: {
      title: 'Running Late Mode',
      icon: 'fa-running',
      color: 'red',
      actions: state.Contingencies.runningLate.actions,
      autoAction: () => {
        UI.showToast('Mode Activated', 'Focus on essentials only', 'warning');
      }
    },
    lowEnergy: {
      title: 'Low Energy Mode',
      icon: 'fa-battery-quarter',
      color: 'yellow',
      actions: state.Contingencies.lowEnergy.actions,
      autoAction: () => {
        setDayType('B');
        UI.showToast('Switched to B-Day', 'Take it easy, focus on baseline', 'info');
      }
    },
    freeTime: {
      title: 'Unexpected Free Time',
      icon: 'fa-gift',
      color: 'green',
      actions: state.Contingencies.freeTime.actions,
      autoAction: () => {
        UI.showToast('Bonus Time!', 'Check your quick wins list', 'success');
      }
    },
    disruption: {
      title: 'Major Disruption',
      icon: 'fa-bolt',
      color: 'purple',
      actions: state.Contingencies.disruption.actions,
      autoAction: () => {
        UI.showToast('Stay Calm', 'Focus on one priority', 'warning');
      }
    }
  };

  const info = contingencyInfo[type];

  const content = `
    <div class="p-6">
      <div class="flex items-center gap-3 mb-4">
        <div class="w-12 h-12 rounded-full bg-${info.color}-100 dark:bg-${info.color}-900/30 flex items-center justify-center">
          <i class="fas ${info.icon} text-${info.color}-600 dark:text-${info.color}-400 text-xl"></i>
        </div>
        <div>
          <h2 class="text-xl font-bold dark:text-white">${info.title}</h2>
          <p class="text-sm text-slate-500 dark:text-gray-400">Contingency plan activated</p>
        </div>
      </div>

      <div class="bg-slate-50 dark:bg-gray-700 rounded-lg p-4 mb-4">
        <h3 class="font-semibold text-sm text-slate-700 dark:text-gray-300 mb-2">Recommended Actions:</h3>
        <ul class="space-y-2">
          ${info.actions.map(action => `
            <li class="flex items-center gap-2 text-sm dark:text-gray-300">
              <i class="fas fa-arrow-right text-${info.color}-500"></i>
              ${action}
            </li>
          `).join('')}
        </ul>
      </div>

      <div class="flex gap-3">
        <button onclick="applyContingency('${type}');UI.closeModal();" class="flex-1 px-4 py-2 bg-${info.color}-600 text-white rounded-lg hover:bg-${info.color}-700">
          Apply & Continue
        </button>
        <button onclick="UI.closeModal()" class="flex-1 px-4 py-2 bg-slate-200 dark:bg-gray-600 dark:text-white rounded-lg hover:bg-slate-300 dark:hover:bg-gray-500">
          Cancel
        </button>
      </div>
    </div>
  `;

  UI.showModal(content);
}

function applyContingency(type) {
  const todayPlan = Helpers.getDayPlan();

  if (type === 'lowEnergy') {
    setDayType('B');
  }

  Helpers.logActivity('contingency_activated', `Activated ${type} contingency plan`, { type });
  UI.showToast('Contingency Applied', 'Your plan has been adjusted', 'success');
}

// Momentum Wins Functions
function addMomentumWin() {
  const content = `
    <div class="p-6">
      <h2 class="text-xl font-bold mb-4 dark:text-white">Log a Win</h2>
      <p class="text-sm text-slate-500 dark:text-gray-400 mb-4">Capture small victories to build momentum</p>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-1 dark:text-gray-300">What did you accomplish?</label>
          <input
            id="momentum-win-text"
            type="text"
            placeholder="e.g., Finished report, had a great meeting..."
            class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2"
          />
        </div>
      </div>
      <div class="flex gap-3 mt-6">
        <button onclick="saveMomentumWin()" class="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
          <i class="fas fa-trophy mr-2"></i>Log Win
        </button>
        <button onclick="UI.closeModal()" class="flex-1 px-4 py-2 bg-slate-200 dark:bg-gray-700 dark:text-white rounded-lg hover:bg-slate-300 dark:hover:bg-gray-600">
          Cancel
        </button>
      </div>
    </div>
  `;
  UI.showModal(content);
  setTimeout(() => document.getElementById('momentum-win-text').focus(), 100);
}

function saveMomentumWin() {
  const text = document.getElementById('momentum-win-text').value.trim();
  if (!text) {
    UI.showToast('Error', 'Please describe your win', 'error');
    return;
  }

  const win = {
    id: stateManager.generateId(),
    text: text,
    timestamp: new Date().toISOString(),
    date: stateManager.getTodayDate()
  };

  state.MomentumWins.push(win);
  stateManager.update({ MomentumWins: state.MomentumWins });
  Helpers.logActivity('momentum_win', `Logged win: ${text}`, { winId: win.id });
  UI.closeModal();
  render();
  UI.showToast('Win Logged!', 'Keep the momentum going!', 'success');
}

function deleteMomentumWin(winId) {
  if (confirm('Delete this win?')) {
    state.MomentumWins = state.MomentumWins.filter(w => w.id !== winId);
    stateManager.update({ MomentumWins: state.MomentumWins });
    render();
    UI.showToast('Win Removed', '', 'info');
  }
}

// Reflection Functions
function openReflectionModal(type) {
  const templates = {
    weekly: {
      title: 'Weekly Reflection',
      prompts: [
        { id: 'wins', label: '3 Biggest Wins This Week', placeholder: 'What went well?' },
        { id: 'challenges', label: 'Challenges Faced', placeholder: 'What was difficult?' },
        { id: 'lessons', label: 'Lessons Learned', placeholder: 'What would you do differently?' },
        { id: 'priorities', label: 'Top 3 Priorities for Next Week', placeholder: 'What matters most?' }
      ]
    },
    monthly: {
      title: 'Monthly Reflection',
      prompts: [
        { id: 'accomplishments', label: 'Key Accomplishments', placeholder: 'What did you achieve?' },
        { id: 'goals_progress', label: 'Goal Progress', placeholder: 'How are your goals progressing?' },
        { id: 'improvements', label: 'Systems to Improve', placeholder: 'What processes need work?' },
        { id: 'focus', label: 'Next Month Focus', placeholder: 'What will you prioritize?' }
      ]
    },
    quarterly: {
      title: 'Quarterly Reflection',
      prompts: [
        { id: 'milestones', label: 'Major Milestones', placeholder: 'Big achievements this quarter?' },
        { id: 'trends', label: 'Trends & Patterns', placeholder: 'What patterns do you notice?' },
        { id: 'growth', label: 'Growth Areas', placeholder: 'How have you grown?' },
        { id: 'strategy', label: 'Next Quarter Strategy', placeholder: 'Strategic focus going forward?' }
      ]
    },
    yearly: {
      title: 'Year-End Review',
      prompts: [
        { id: 'top5', label: 'Top 5 Achievements', placeholder: 'Your biggest wins this year?' },
        { id: 'transformation', label: 'Personal Transformation', placeholder: 'How have you changed?' },
        { id: 'gratitude', label: 'Gratitude', placeholder: 'What are you grateful for?' },
        { id: 'vision', label: 'Vision for Next Year', placeholder: 'What do you want to accomplish?' }
      ]
    }
  };

  const template = templates[type];
  const content = `
    <div class="p-6 max-h-[80vh] overflow-y-auto">
      <h2 class="text-xl font-bold mb-4 dark:text-white">${template.title}</h2>
      <p class="text-sm text-slate-500 dark:text-gray-400 mb-6">Take time to reflect on your progress</p>

      <div class="space-y-4">
        ${template.prompts.map(prompt => `
          <div>
            <label class="block text-sm font-medium mb-1 dark:text-gray-300">${prompt.label}</label>
            <textarea
              id="reflection-${prompt.id}"
              placeholder="${prompt.placeholder}"
              class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2"
              rows="3"
            ></textarea>
          </div>
        `).join('')}

        <div>
          <label class="block text-sm font-medium mb-1 dark:text-gray-300">Overall Mood</label>
          <select id="reflection-mood" class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2">
            <option value="">Select mood...</option>
            <option value="excellent">Excellent</option>
            <option value="good">Good</option>
            <option value="neutral">Neutral</option>
            <option value="challenging">Challenging</option>
            <option value="difficult">Difficult</option>
          </select>
        </div>
      </div>

      <div class="flex gap-3 mt-6">
        <button onclick="saveReflection('${type}')" class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          Save Reflection
        </button>
        <button onclick="UI.closeModal()" class="flex-1 px-4 py-2 bg-slate-200 dark:bg-gray-700 dark:text-white rounded-lg hover:bg-slate-300 dark:hover:bg-gray-600">
          Cancel
        </button>
      </div>
    </div>
  `;

  UI.showModal(content);
}

function saveReflection(type) {
  const prompts = {
    weekly: ['wins', 'challenges', 'lessons', 'priorities'],
    monthly: ['accomplishments', 'goals_progress', 'improvements', 'focus'],
    quarterly: ['milestones', 'trends', 'growth', 'strategy'],
    yearly: ['top5', 'transformation', 'gratitude', 'vision']
  };

  const reflection = {
    id: stateManager.generateId(),
    type: type,
    timestamp: new Date().toISOString(),
    mood: document.getElementById('reflection-mood').value,
    responses: {}
  };

  prompts[type].forEach(promptId => {
    const value = document.getElementById(`reflection-${promptId}`).value.trim();
    if (value) {
      reflection.responses[promptId] = value;
    }
  });

  if (Object.keys(reflection.responses).length === 0) {
    UI.showToast('Error', 'Please fill in at least one field', 'error');
    return;
  }

  state.Reflections[type].push(reflection);
  stateManager.update({ Reflections: state.Reflections });
  Helpers.logActivity('reflection_created', `Created ${type} reflection`, { type });
  UI.closeModal();
  render();
  UI.showToast('Reflection Saved', `Your ${type} reflection has been recorded`, 'success');
}

function deleteReflection(type, reflectionId) {
  if (confirm('Delete this reflection?')) {
    state.Reflections[type] = state.Reflections[type].filter(r => r.id !== reflectionId);
    stateManager.update({ Reflections: state.Reflections });
    render();
    UI.showToast('Reflection Deleted', '', 'warning');
  }
}

function setReflectionTab(tab) {
  state.reflectionTab = tab;
  render();
}

function switchJournalType(type, entryId) {
  UI.closeModal();
  setTimeout(() => openJournalModal(entryId || null, type), 100);
}

function deleteActivity(activityId) {
  if (confirm('Delete this activity from your timeline?')) {
    state.History.timeline = state.History.timeline.filter(a => a.id !== activityId);
    stateManager.update({ History: state.History });
    render();
    UI.showToast('Activity Deleted', 'Removed from timeline', 'warning');
  }
}

function exportTimeline() {
  if (!state.History.timeline || state.History.timeline.length === 0) {
    UI.showToast('No Data', 'Timeline is empty', 'warning');
    return;
  }
  
  const sortedActivities = [...state.History.timeline].sort((a, b) => 
    new Date(b.timestamp) - new Date(a.timestamp)
  );
  
  let text = 'CYCLEBOARD ACTIVITY TIMELINE\n';
  text += '='.repeat(50) + '\n\n';
  
  const groupedByDate = {};
  sortedActivities.forEach(activity => {
    const date = new Date(activity.timestamp).toISOString().slice(0, 10);
    if (!groupedByDate[date]) groupedByDate[date] = [];
    groupedByDate[date].push(activity);
  });
  
  Object.keys(groupedByDate).forEach(date => {
    const dateObj = new Date(date);
    text += `ðŸ“… ${dateObj.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}\n`;
    text += '-'.repeat(50) + '\n';
    
    groupedByDate[date].forEach(activity => {
      const time = new Date(activity.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
      text += `${time} - ${activity.description}\n`;
      if (activity.details.note) {
        text += `  Note: ${activity.details.note}\n`;
      }
    });
    
    text += '\n';
  });
  
  const dataBlob = new Blob([text], { type: 'text/plain' });
  const url = URL.createObjectURL(dataBlob);
  
  const link = document.createElement('a');
  link.href = url;
  link.download = `cycleboard-timeline-${new Date().toISOString().slice(0, 10)}.txt`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  
  UI.showToast('Timeline Exported', 'Downloaded as text file', 'success');
}

function init() {
  const menuToggle = document.getElementById('mobile-menu-toggle');
  if (menuToggle) {
    menuToggle.addEventListener('click', () => {
      const sidebar = document.getElementById('sidebar');
      const isHidden = sidebar.classList.contains('hidden');
      if (isHidden) {
        sidebar.classList.remove('hidden');
        sidebar.classList.add('block');
      } else {
        sidebar.classList.add('hidden');
        sidebar.classList.remove('block');
      }
    });
  }
  
  // Close sidebar when clicking outside on mobile
  document.addEventListener('click', (e) => {
    const sidebar = document.getElementById('sidebar');
    const menuToggle = document.getElementById('mobile-menu-toggle');
    if (sidebar && !sidebar.contains(e.target) && !menuToggle.contains(e.target) && window.innerWidth < 768) {
      sidebar.classList.add('hidden');
      sidebar.classList.remove('block');
    }
  });
  
  UI.updateDateDisplay();
  
  if (state.Settings.darkMode) {
    document.documentElement.classList.add('dark');
    document.body.classList.add('bg-gray-900', 'text-white');
    document.body.classList.remove('bg-slate-50');
  }
  
  render();

  // Periodic backup save every 5 minutes (in case debounce fails)
  setInterval(() => {
    if (state.Settings.autoSave) {
      stateManager.saveToStorage();
    }
  }, 300000);

  // Save before page unload
  window.addEventListener('beforeunload', () => {
    stateManager.saveToStorage();
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Skip if user is typing in an input field
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
      // Allow Ctrl+S even in input fields
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        e.stopPropagation();
        stateManager.saveToStorage();
        UI.showToast('Saved', 'Data saved successfully', 'success');
      }
      return;
    }

    // Global shortcuts
    if (e.ctrlKey || e.metaKey) {
      switch(e.key.toLowerCase()) {
        case 's':
          e.preventDefault();
          e.stopPropagation();
          stateManager.saveToStorage();
          UI.showToast('Saved', 'Data saved successfully', 'success');
          break;
        case 'e':
          e.preventDefault();
          e.stopPropagation();
          exportState();
          break;
        case 'n':
        case 'k':
          e.preventDefault();
          e.stopPropagation();
          if (state.screen === 'AtoZ') {
            openCreateModal();
          } else if (state.screen === 'Daily') {
            addTimeBlock();
          } else {
            UI.showToast('Quick Add', 'Navigate to A-Z or Daily to use this shortcut', 'info');
          }
          break;
        case 'z':
          e.preventDefault();
          if (e.shiftKey) {
            // Redo with Ctrl+Shift+Z
            if (stateManager.redo()) {
              UI.showToast('Redone', 'Action redone', 'info');
              render();
            } else {
              UI.showToast('Nothing to Redo', '', 'warning');
            }
          } else {
            // Undo with Ctrl+Z
            if (stateManager.undo()) {
              UI.showToast('Undone', 'Action undone', 'info');
              render();
            } else {
              UI.showToast('Nothing to Undo', '', 'warning');
            }
          }
          break;
        case 'y':
          // Redo with Ctrl+Y (alternative)
          e.preventDefault();
          if (stateManager.redo()) {
            UI.showToast('Redone', 'Action redone', 'info');
            render();
          } else {
            UI.showToast('Nothing to Redo', '', 'warning');
          }
          break;
      }
    } else {
      // Navigation shortcuts (no modifier key)
      switch(e.key.toLowerCase()) {
        case 'h':
          navigate('Home');
          break;
        case 'd':
          navigate('Daily');
          break;
        case 'a':
          navigate('AtoZ');
          break;
        case 'w':
          navigate('WeeklyFocus');
          break;
        case 't':
          navigate('Timeline');
          break;
        case 'r':
          navigate('Routines');
          break;
        case 's':
          navigate('Statistics');
          break;
        case 'escape':
          UI.closeModal();
          break;
        case '?':
          showKeyboardShortcutsHelp();
          break;
        case 'q':
          openQuickEntryModal();
          break;
      }
    }
  });
}

function showKeyboardShortcutsHelp() {
  const content = `
    <div class="p-6">
      <h2 class="text-xl font-bold mb-4 dark:text-white">Keyboard Shortcuts</h2>
      <div class="space-y-4">
        <div>
          <h3 class="font-semibold text-sm text-slate-600 dark:text-gray-400 mb-2">Navigation</h3>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <div class="flex justify-between"><span class="dark:text-gray-300">Home</span><kbd class="px-2 py-1 bg-slate-100 dark:bg-gray-700 rounded">H</kbd></div>
            <div class="flex justify-between"><span class="dark:text-gray-300">Daily</span><kbd class="px-2 py-1 bg-slate-100 dark:bg-gray-700 rounded">D</kbd></div>
            <div class="flex justify-between"><span class="dark:text-gray-300">A-Z Tasks</span><kbd class="px-2 py-1 bg-slate-100 dark:bg-gray-700 rounded">A</kbd></div>
            <div class="flex justify-between"><span class="dark:text-gray-300">Weekly Focus</span><kbd class="px-2 py-1 bg-slate-100 dark:bg-gray-700 rounded">W</kbd></div>
            <div class="flex justify-between"><span class="dark:text-gray-300">Timeline</span><kbd class="px-2 py-1 bg-slate-100 dark:bg-gray-700 rounded">T</kbd></div>
            <div class="flex justify-between"><span class="dark:text-gray-300">Routines</span><kbd class="px-2 py-1 bg-slate-100 dark:bg-gray-700 rounded">R</kbd></div>
            <div class="flex justify-between"><span class="dark:text-gray-300">Statistics</span><kbd class="px-2 py-1 bg-slate-100 dark:bg-gray-700 rounded">S</kbd></div>
          </div>
        </div>
        <div>
          <h3 class="font-semibold text-sm text-slate-600 dark:text-gray-400 mb-2">Actions</h3>
          <div class="grid grid-cols-1 gap-2 text-sm">
            <div class="flex justify-between"><span class="dark:text-gray-300">Save Data</span><kbd class="px-2 py-1 bg-slate-100 dark:bg-gray-700 rounded">Ctrl+S</kbd></div>
            <div class="flex justify-between"><span class="dark:text-gray-300">Export Data</span><kbd class="px-2 py-1 bg-slate-100 dark:bg-gray-700 rounded">Ctrl+E</kbd></div>
            <div class="flex justify-between"><span class="dark:text-gray-300">New Task/Block</span><kbd class="px-2 py-1 bg-slate-100 dark:bg-gray-700 rounded">Ctrl+K / Ctrl+N</kbd></div>
            <div class="flex justify-between"><span class="dark:text-gray-300">Undo</span><kbd class="px-2 py-1 bg-slate-100 dark:bg-gray-700 rounded">Ctrl+Z</kbd></div>
            <div class="flex justify-between"><span class="dark:text-gray-300">Redo</span><kbd class="px-2 py-1 bg-slate-100 dark:bg-gray-700 rounded">Ctrl+Y / Ctrl+Shift+Z</kbd></div>
            <div class="flex justify-between"><span class="dark:text-gray-300">Close Modal</span><kbd class="px-2 py-1 bg-slate-100 dark:bg-gray-700 rounded">Esc</kbd></div>
            <div class="flex justify-between"><span class="dark:text-gray-300">Quick Entry</span><kbd class="px-2 py-1 bg-slate-100 dark:bg-gray-700 rounded">Q</kbd></div>
            <div class="flex justify-between"><span class="dark:text-gray-300">Show Shortcuts</span><kbd class="px-2 py-1 bg-slate-100 dark:bg-gray-700 rounded">?</kbd></div>
          </div>
        </div>
      </div>
      <div class="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
        <p class="text-xs text-yellow-800 dark:text-yellow-300">
          <i class="fas fa-info-circle mr-1"></i>
          <strong>Note:</strong> Some browsers may block Ctrl+N (opens new tab). Use Ctrl+K as an alternative.
        </p>
      </div>
      <div class="mt-6 flex justify-end">
        <button onclick="UI.closeModal()" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          Got it!
        </button>
      </div>
    </div>
  `;
  UI.showModal(content);
}

// Quick Entry Modal
function openQuickEntryModal() {
  const content = `
    <div class="p-6">
      <h2 class="text-xl font-bold mb-4 dark:text-white">Quick Entry</h2>
      <p class="text-sm text-slate-500 dark:text-gray-400 mb-6">Choose an action to perform</p>
      <div class="space-y-3">
        <button onclick="quickAddTask();UI.closeModal();" class="w-full flex items-center gap-4 p-4 border dark:border-gray-600 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700 transition-colors text-left">
          <div class="w-12 h-12 rounded-full bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400 flex items-center justify-center flex-shrink-0">
            <i class="fas fa-plus-circle text-xl"></i>
          </div>
          <div class="flex-1">
            <p class="font-medium dark:text-gray-300">Quick Task</p>
            <p class="text-sm text-slate-500 dark:text-gray-400">Add a simple A-Z task</p>
          </div>
          <i class="fas fa-chevron-right text-slate-400 dark:text-gray-500"></i>
        </button>

        <button onclick="quickAddTimeBlock();UI.closeModal();" class="w-full flex items-center gap-4 p-4 border dark:border-gray-600 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700 transition-colors text-left">
          <div class="w-12 h-12 rounded-full bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400 flex items-center justify-center flex-shrink-0">
            <i class="fas fa-clock text-xl"></i>
          </div>
          <div class="flex-1">
            <p class="font-medium dark:text-gray-300">Quick Time Block</p>
            <p class="text-sm text-slate-500 dark:text-gray-400">Add a time block to today</p>
          </div>
          <i class="fas fa-chevron-right text-slate-400 dark:text-gray-500"></i>
        </button>

        <button onclick="showRoutineSelector();UI.closeModal();" class="w-full flex items-center gap-4 p-4 border dark:border-gray-600 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700 transition-colors text-left">
          <div class="w-12 h-12 rounded-full bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400 flex items-center justify-center flex-shrink-0">
            <i class="fas fa-check-circle text-xl"></i>
          </div>
          <div class="flex-1">
            <p class="font-medium dark:text-gray-300">Mark Routine Done</p>
            <p class="text-sm text-slate-500 dark:text-gray-400">Complete a routine</p>
          </div>
          <i class="fas fa-chevron-right text-slate-400 dark:text-gray-500"></i>
        </button>

        <button onclick="quickSetGoal();UI.closeModal();" class="w-full flex items-center gap-4 p-4 border dark:border-gray-600 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700 transition-colors text-left">
          <div class="w-12 h-12 rounded-full bg-yellow-100 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400 flex items-center justify-center flex-shrink-0">
            <i class="fas fa-bullseye text-xl"></i>
          </div>
          <div class="flex-1">
            <p class="font-medium dark:text-gray-300">Set Today's Goal</p>
            <p class="text-sm text-slate-500 dark:text-gray-400">Define today's focus</p>
          </div>
          <i class="fas fa-chevron-right text-slate-400 dark:text-gray-500"></i>
        </button>
      </div>
      <div class="mt-6 flex justify-end">
        <button onclick="UI.closeModal()" class="px-4 py-2 bg-slate-200 dark:bg-gray-700 dark:text-white rounded-lg hover:bg-slate-300 dark:hover:bg-gray-600">
          Cancel
        </button>
      </div>
    </div>
  `;
  UI.showModal(content);
}

function quickAddTask() {
  openCreateModal();
}

function quickAddTimeBlock() {
  navigate('Daily');
  setTimeout(() => addTimeBlock(), 300);
}

function showRoutineSelector() {
  navigate('Routines');
}

function quickSetGoal() {
  const todayPlan = Helpers.getDayPlan();
  const content = `
    <div class="p-6">
      <h2 class="text-xl font-bold mb-4 dark:text-white">Set Today's Goal</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-1 dark:text-gray-300">Baseline Goal</label>
          <input
            id="quick-baseline"
            type="text"
            value="${UI.sanitize(todayPlan.baseline_goal.text)}"
            class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2"
            placeholder="What's your minimum win for today?"
          />
        </div>
        <div>
          <label class="block text-sm font-medium mb-1 dark:text-gray-300">Stretch Goal (Optional)</label>
          <input
            id="quick-stretch"
            type="text"
            value="${UI.sanitize(todayPlan.stretch_goal.text)}"
            class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2"
            placeholder="What would make today amazing?"
          />
        </div>
      </div>
      <div class="flex gap-3 mt-6">
        <button onclick="saveQuickGoal()" class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          Save Goals
        </button>
        <button onclick="UI.closeModal()" class="flex-1 px-4 py-2 bg-slate-200 dark:bg-gray-700 dark:text-white rounded-lg hover:bg-slate-300 dark:hover:bg-gray-600">
          Cancel
        </button>
      </div>
    </div>
  `;
  UI.showModal(content);
  setTimeout(() => document.getElementById('quick-baseline').focus(), 100);
}

function saveQuickGoal() {
  const baseline = document.getElementById('quick-baseline').value.trim();
  const stretch = document.getElementById('quick-stretch').value.trim();

  if (!baseline) {
    UI.showToast('Error', 'Please set a baseline goal', 'error');
    return;
  }

  const todayPlan = Helpers.getDayPlan();
  todayPlan.baseline_goal.text = baseline;
  todayPlan.stretch_goal.text = stretch;

  state.DayPlans[todayPlan.date] = todayPlan;
  stateManager.update({ DayPlans: state.DayPlans });

  UI.closeModal();
  UI.showToast('Goals Set', 'Today\'s goals have been updated', 'success');
  Helpers.logActivity('goals_set', `Set goals: ${baseline}`, { baseline, stretch });
}

function render() {
  state = stateManager.getState();
  renderNav();
  UI.updateDateDisplay();
  
  const content = document.getElementById('main-content');
  if (content) {
    const screenContainer = content.querySelector('.max-w-6xl') || content;
    screenContainer.innerHTML = ScreenRenderers[state.screen]();

    if (state.screen === 'AtoZ') {
      const input = document.getElementById('az-search-input');
      if (input && getAzSearch() !== '') {
        input.focus();
        const val = input.value;
        input.value = '';
        input.value = val;
      }
    }
  }
}
// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    completeTask, deleteTask, setDayType, openDayTypeTemplateEditor, saveDayTypeTemplate,
    applyTemplateToToday, addTimeBlock, updateTimeBlock, toggleTimeBlockCompletion,
    removeTimeBlock, saveGoals, toggleGoalCompletion, openCreateModal, openEditModal,
    sortTasks, filterTasks, searchTasks, exportState, showImportModal, handleFileImport,
    clearData, resetToDefaults, toggleDarkMode, toggleSetting, updateSetting,
    addRoutineStep, updateRoutineStep, deleteRoutineStep, moveRoutineStep,
    addNewRoutineType, deleteRoutineType, toggleRoutineStep, toggleRoutineComplete,
    openJournalModal, saveJournalEntry, editJournalEntry, deleteJournalEntry,
    addFocusTask, toggleFocusTask, removeFocusTask, toggleEightStep,
    activateContingency, addMomentumWin, deleteMomentumWin, setReflectionTab,
    openReflectionModal, saveReflection, deleteReflection, deleteActivity,
    exportTimeline, completeAllTodayTasks, init, render, convertTo24Hour
  };
}
