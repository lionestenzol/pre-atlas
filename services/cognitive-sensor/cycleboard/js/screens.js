// Atlas Dashboard Screens Module
// Navigation and Screen Renderers
const screens = [
  { id: 'Command', label: 'Command', icon: 'fa-terminal' },
  { id: 'Home', label: 'Home', icon: 'fa-home' },
  { id: 'Daily', label: 'Daily', icon: 'fa-calendar-day' },
  { id: 'AtoZ', label: 'A–Z', icon: 'fa-tasks' },
  { id: 'WeeklyFocus', label: 'Weekly Focus', icon: 'fa-bullseye' },
  { id: 'Routines', label: 'Routines', icon: 'fa-clock' },
  { id: 'Journal', label: 'Journal', icon: 'fa-book' },
  { id: 'Reflections', label: 'Reflections', icon: 'fa-lightbulb' },
  { id: 'Energy', label: 'Energy', icon: 'fa-battery-three-quarters' },
  { id: 'Finance', label: 'Finance', icon: 'fa-wallet' },
  { id: 'Skills', label: 'Skills', icon: 'fa-graduation-cap' },
  { id: 'Network', label: 'Network', icon: 'fa-users' },
  { id: 'OSINT', label: 'OSINT', icon: 'fa-satellite-dish' },
  { id: 'Statistics', label: 'Statistics', icon: 'fa-chart-line' },
  { id: 'Timeline', label: 'Timeline', icon: 'fa-history' },
  { id: 'Settings', label: 'Settings', icon: 'fa-cog' }
];

function renderNav() {
  const nav = document.getElementById('nav');
  if (!nav) return;
  
  nav.innerHTML = screens.map(s => `
    <button
      onclick="navigate('${s.id}')"
      class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm w-full text-left transition-colors ${state.screen === s.id ? 'bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-900/30 dark:border-blue-800 dark:text-blue-300' : 'hover:bg-slate-50 dark:hover:bg-gray-700 text-slate-700 dark:text-gray-300'}"
    >
      <i class="fas ${s.icon} w-5 h-5"></i>
      <span>${s.label}</span>
      ${s.id === 'Home' && Helpers.calculateCompletionPercentage() > 0 ? `
        <span class="ml-auto text-xs font-semibold px-2 py-1 rounded-full ${Helpers.calculateCompletionPercentage() >= 70 ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300' : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300'}">
          ${Helpers.calculateCompletionPercentage()}%
        </span>
      ` : ''}
    </button>
  `).join('') + `
    <div class="mt-4 pt-4 border-t dark:border-gray-700">
      <p class="text-xs uppercase tracking-wider text-slate-400 dark:text-gray-500 px-3 mb-2">System</p>
      <div class="flex gap-1 px-2">
        <button onclick="AtlasNav.open('control')" class="flex-1 p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-gray-700 text-slate-500 dark:text-gray-400 transition" title="Control Panel">
          <i class="fas fa-sliders-h"></i>
        </button>
        <button onclick="AtlasNav.open('atlas')" class="flex-1 p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-gray-700 text-slate-500 dark:text-gray-400 transition" title="Cognitive Atlas">
          <i class="fas fa-project-diagram"></i>
        </button>
        <button onclick="AtlasNav.open('ideas')" class="flex-1 p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-gray-700 text-slate-500 dark:text-gray-400 transition" title="Idea Registry">
          <i class="fas fa-lightbulb"></i>
        </button>
      </div>
    </div>
  `;
  
  }

function navigate(screen) {
  state.screen = screen;
  stateManager.update({ screen: state.screen });
  render();
  
  const sidebar = document.getElementById('sidebar');
  if (sidebar && sidebar.classList.contains('block')) {
    sidebar.classList.remove('block');
    sidebar.classList.add('hidden');
  }
}

const ScreenRenderers = {
  Home() {
    
    
    
    
    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <h1 class="text-3xl font-bold tracking-tight dark:text-white">Atlas Dashboard</h1>
          <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">${Helpers.formatDate(stateManager.getTodayDate())} • System governance overview</p>
        </div>

        ${typeof BrainData !== 'undefined' ? (() => {
          const el = BrainData.getEnergyLevel();
          const ml = BrainData.getMentalLoad();
          const rw = BrainData.getRunwayMonths();
          const sk = BrainData.getSkillsUtilization();
          const nw = BrainData.getNetworkScore();
          const phase = BrainData.getLifePhaseName();
          const burnout = BrainData.getBurnoutRisk();
          const redAlert = BrainData.getRedAlertActive();

          const energyColor = el >= 70 ? 'text-green-400' : el >= 30 ? 'text-yellow-400' : 'text-red-400';
          const finColor = rw >= 6 ? 'text-green-400' : rw >= 2 ? 'text-yellow-400' : 'text-red-400';
          const skillColor = sk >= 70 ? 'text-green-400' : sk >= 40 ? 'text-yellow-400' : 'text-red-400';
          const netColor = nw >= 60 ? 'text-green-400' : nw >= 20 ? 'text-yellow-400' : 'text-red-400';

          return `
            <div class="rounded-xl border dark:border-gray-700 bg-gray-900 p-4 shadow-sm mb-2 ${redAlert ? 'ring-2 ring-red-500/50' : ''}">
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-2">
                  <i class="fas fa-satellite-dish text-blue-400"></i>
                  <span class="text-xs font-semibold uppercase tracking-wider text-gray-400">Strategic HUD</span>
                </div>
                <span class="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-300">Phase ${BrainData.getLifePhase()}: ${phase}</span>
              </div>
              <div class="grid grid-cols-5 gap-3">
                <button onclick="navigate('Energy')" class="text-center p-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition cursor-pointer">
                  <i class="fas fa-bolt ${energyColor} text-lg"></i>
                  <p class="text-lg font-bold ${energyColor} mt-1">${el}</p>
                  <p class="text-[10px] text-gray-500 uppercase">Energy</p>
                  ${burnout ? '<p class="text-[9px] text-red-400 mt-0.5">BURNOUT</p>' : ''}
                </button>
                <button onclick="navigate('Finance')" class="text-center p-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition cursor-pointer">
                  <i class="fas fa-wallet ${finColor} text-lg"></i>
                  <p class="text-lg font-bold ${finColor} mt-1">${rw.toFixed(1)}mo</p>
                  <p class="text-[10px] text-gray-500 uppercase">Runway</p>
                </button>
                <button onclick="navigate('Skills')" class="text-center p-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition cursor-pointer">
                  <i class="fas fa-graduation-cap ${skillColor} text-lg"></i>
                  <p class="text-lg font-bold ${skillColor} mt-1">${Math.round(sk)}%</p>
                  <p class="text-[10px] text-gray-500 uppercase">Skills</p>
                </button>
                <button onclick="navigate('Network')" class="text-center p-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition cursor-pointer">
                  <i class="fas fa-users ${netColor} text-lg"></i>
                  <p class="text-lg font-bold ${netColor} mt-1">${nw}</p>
                  <p class="text-[10px] text-gray-500 uppercase">Network</p>
                </button>
                <div class="text-center p-2 rounded-lg bg-gray-800">
                  <i class="fas fa-brain text-purple-400 text-lg"></i>
                  <p class="text-lg font-bold text-purple-400 mt-1">${ml}/10</p>
                  <p class="text-[10px] text-gray-500 uppercase">Load</p>
                </div>
              </div>
              ${redAlert ? '<div class="mt-2 text-xs text-center text-red-400 font-medium"><i class="fas fa-exclamation-triangle mr-1"></i>RED ALERT ZONE — Predicted interference window active</div>' : ''}
            </div>
          `;
        })() : ''}

        

          <div class="rounded-xl bg-white dark:bg-gray-800 p-6 shadow-sm border dark:border-gray-700">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-slate-500 dark:text-gray-400">Active Days</p>
                <p class="text-3xl font-bold mt-1 dark:text-white">${monthlyStats.days}</p>
              </div>
              <i class="fas fa-calendar-check text-3xl text-blue-500"></i>
            </div>
            <p class="text-sm text-slate-600 dark:text-gray-300 mt-2">${Math.round(monthlyStats.days / 30 * 100)}% of days planned</p>
          </div>

          <div class="rounded-xl bg-white dark:bg-gray-800 p-6 shadow-sm border dark:border-gray-700">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-slate-500 dark:text-gray-400">Weekly Success</p>
                <p class="text-3xl font-bold mt-1 dark:text-white">${weeklyStats.percentage}%</p>
              </div>
              <i class="fas fa-chart-line text-3xl text-green-500"></i>
            </div>
            <p class="text-sm text-slate-600 dark:text-gray-300 mt-2">${weeklyStats.completed}/${weeklyStats.total} days met goals</p>
          </div>
        </div>

        <div class="grid md:grid-cols-2 gap-6">
          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <h3 class="text-lg font-bold mb-4 dark:text-white">Task Status Distribution</h3>
            <div class="space-y-3">
              ${[
                { label: 'Completed', value: state.AZTask.filter(t => t.status === 'Completed').length, color: 'bg-green-500' },
                { label: 'In Progress', value: state.AZTask.filter(t => t.status === 'In Progress').length, color: 'bg-blue-500' },
                { label: 'Not Started', value: state.AZTask.filter(t => t.status === 'Not Started').length, color: 'bg-slate-500 dark:bg-gray-500' }
              ].map(item => `
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <div class="w-3 h-3 rounded-full ${item.color}"></div>
                    <span class="dark:text-gray-300">${item.label}</span>
                  </div>
                  <div class="flex items-center gap-3">
                    <span class="font-medium dark:text-gray-300">${item.value}</span>
                    <div class="w-32 bg-slate-200 dark:bg-gray-700 rounded-full h-2">
                      <div class="h-2 rounded-full ${item.color}" 
                           style="width: ${state.AZTask.length ? (item.value / state.AZTask.length) * 100 : 0}%">
                      </div>
                    </div>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>

          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <h3 class="text-lg font-bold mb-4 dark:text-white">Day Type Usage</h3>
            <div class="space-y-3">
              ${['A', 'B', 'C'].map(type => {
                const count = Object.values(state.DayPlans).filter(p => p.day_type === type).length;
                const total = Object.keys(state.DayPlans).length;
                return `
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <div class="w-8 h-8 rounded-lg ${
                        type === 'A' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' :
                        type === 'B' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
                        'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
                      } flex items-center justify-center font-bold">
                        ${type}
                      </div>
                      <span class="dark:text-gray-300">${type} Days</span>
                    </div>
                    <div class="flex items-center gap-3">
                      <span class="font-medium dark:text-gray-300">${count}</span>
                      <div class="w-32 bg-slate-200 dark:bg-gray-700 rounded-full h-2">
                        <div class="h-2 rounded-full ${
                          type === 'A' ? 'bg-blue-500' :
                          type === 'B' ? 'bg-green-500' :
                          'bg-purple-500'
                        }" style="width: ${total ? (count / total) * 100 : 0}%"></div>
                      </div>
                    </div>
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        </div>

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
          <h3 class="text-lg font-bold mb-4 dark:text-white">Recent Activity</h3>
          <div class="space-y-3">
            ${state.AZTask
              .filter(t => t.status === 'Completed')
              .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
              .slice(0, 5)
              .map(task => `
                <div class="flex items-center gap-3 p-3 rounded-lg bg-green-50 dark:bg-green-900/20">
                  <div class="w-8 h-8 rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300 flex items-center justify-center">
                    <i class="fas fa-check"></i>
                  </div>
                  <div class="flex-1">
                    <p class="font-medium dark:text-gray-300">Completed: ${task.letter} - ${UI.sanitize(task.task)}</p>
                    <p class="text-sm text-slate-500 dark:text-gray-400">${new Date(task.createdAt).toLocaleDateString()}</p>
                  </div>
                </div>
              `).join('')}
            
            ${state.AZTask.filter(t => t.status === 'Completed').length === 0 ? `
              <p class="text-center text-slate-500 dark:text-gray-400 py-4">No completed tasks yet</p>
            ` : ''}
          </div>
        </div>

        ${(() => {
          const headline = BrainData.governorHeadline;
          const cogState = CognitiveController.payload;
          if (!headline && !cogState) return '';
          const driftScore = headline?.drift_score ?? 0;
          const driftAlerts = headline?.drift_alerts || [];
          const compliance = headline?.compliance_rate ?? 0;
          const closureRatio = cogState?.closure?.ratio ?? '--';
          const openLoops = cogState?.closure?.open ?? '--';
          const mode = CognitiveController.getMode ? CognitiveController.getMode() : '--';
          const driftColor = driftScore >= 6 ? 'text-red-500' : driftScore >= 3 ? 'text-yellow-500' : 'text-green-500';
          const modeColor = mode === 'CLOSURE' ? 'text-red-500' : mode === 'MAINTENANCE' ? 'text-yellow-500' : mode === 'BUILD' ? 'text-green-500' : 'text-slate-500';
          return `
          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
            <div class="p-6 border-b dark:border-gray-700">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <i class="fas fa-brain text-indigo-500"></i>
                  <h2 class="text-lg font-bold dark:text-white">Cognitive Health</h2>
                </div>
                <button onclick="AtlasNav.open('atlas')" class="text-xs text-blue-600 dark:text-blue-400 hover:underline">Full atlas →</button>
              </div>
            </div>
            <div class="p-6">
              <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center mb-4">
                <div>
                  <div class="text-xs text-slate-500 dark:text-gray-400">Mode</div>
                  <div class="text-lg font-bold ${modeColor}">${mode}</div>
                </div>
                <div>
                  <div class="text-xs text-slate-500 dark:text-gray-400">Closure Ratio</div>
                  <div class="text-lg font-bold dark:text-white">${typeof closureRatio === 'number' ? closureRatio.toFixed(1) + '%' : closureRatio}</div>
                </div>
                <div>
                  <div class="text-xs text-slate-500 dark:text-gray-400">Drift Score</div>
                  <div class="text-lg font-bold ${driftColor}">${driftScore}/10</div>
                </div>
                <div>
                  <div class="text-xs text-slate-500 dark:text-gray-400">Compliance</div>
                  <div class="text-lg font-bold dark:text-white">${compliance}%</div>
                </div>
              </div>
              ${driftAlerts.length > 0 ? `
                <div class="space-y-2">
                  ${driftAlerts.map(a => `
                    <div class="p-2 rounded-lg ${a.severity === 'HIGH' ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300' : 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-300'} text-sm">
                      <i class="fas fa-exclamation-triangle mr-1"></i>${UI.sanitize(a.message || a.type)}
                    </div>
                  `).join('')}
                </div>
              ` : '<p class="text-sm text-green-600 dark:text-green-400"><i class="fas fa-check-circle mr-1"></i>No drift alerts</p>'}
            </div>
          </div>`;
        })()}
      </div>
    `;
  },



  Daily() {
    const todayPlan = Helpers.getDayPlan();
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const yesterdayStr = yesterday.toISOString().slice(0, 10);
    const yesterdayPlan = state.DayPlans[yesterdayStr];
    const dailyProgress = Helpers.calculateDailyProgress();

    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <div class="flex items-center justify-between">
            <div>
              <h1 class="text-3xl font-bold tracking-tight dark:text-white">Daily Plan</h1>
              <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">${Helpers.formatDate(todayPlan.date)}</p>
            </div>
            <div class="flex items-center gap-4">
              <div class="text-right hidden md:block">
                <div class="text-2xl font-bold ${
                  dailyProgress.overall >= 80 ? 'text-green-600 dark:text-green-400' :
                  dailyProgress.overall >= 50 ? 'text-blue-600 dark:text-blue-400' :
                  'text-slate-400 dark:text-gray-500'
                }">${dailyProgress.overall}%</div>
                <p class="text-xs text-slate-500 dark:text-gray-400">Progress</p>
              </div>
              <button onclick="addTimeBlock()" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                <i class="fas fa-plus mr-2"></i>Add Block
              </button>
            </div>
          </div>
        </div>

        <div class="rounded-xl border-2 ${
          dailyProgress.overall >= 80 ? 'border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20' :
          dailyProgress.overall >= 50 ? 'border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20' :
          'border-slate-200 dark:border-gray-700 bg-white dark:bg-gray-800'
        } p-5 shadow-sm">
          <div class="flex items-center justify-between mb-3">
            <h3 class="font-semibold dark:text-white">Today's Completion</h3>
            <span class="text-xl font-bold ${
              dailyProgress.overall >= 80 ? 'text-green-600 dark:text-green-400' :
              dailyProgress.overall >= 50 ? 'text-blue-600 dark:text-blue-400' :
              'text-slate-500 dark:text-gray-400'
            }">${dailyProgress.overall}%</span>
          </div>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            ${dailyProgress.breakdown.map(item => `
              <div class="flex items-center gap-2">
                <i class="fas ${item.icon} ${UI.getColorClass(item.color, 'text')} ${UI.getColorClass(item.color, 'textDark')}"></i>
                <span class="text-slate-700 dark:text-gray-300">${item.label}:</span>
                <span class="font-semibold dark:text-white">${item.completed}/${item.total}</span>
              </div>
            `).join('')}
          </div>
        </div>

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
          <h2 class="text-xl font-bold mb-4 dark:text-white">Day Mode</h2>
          <div class="flex flex-wrap gap-2">
            ${['A', 'B', 'C'].map(type => `
              <button
                onclick="setDayType('${type}')"
                class="px-6 py-3 rounded-lg font-medium transition-all ${
                  todayPlan.day_type === type 
                    ? 'bg-blue-600 text-white shadow-md' 
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
                }"
              >
                ${type} Day
                ${type === 'A' ? ' (Deep Focus)' : type === 'B' ? ' (Balanced)' : ' (Recovery)'}
              </button>
            `).join('')}
          </div>
        </div>

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
          <div class="p-6 border-b dark:border-gray-700">
            <h2 class="text-xl font-bold dark:text-white">Time Blocks</h2>
            <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Schedule your day</p>
          </div>
          <div class="p-6">
            <div class="space-y-3">
              ${todayPlan.time_blocks.map((block, index) => `
                <div class="flex items-center gap-3 p-3 rounded-lg border dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-500 transition-colors">
                  <input
                    type="time"
                    value="${convertTo24Hour(block.time)}"
                    onchange="updateTimeBlock('${block.id}', 'time', this.value)"
                    class="font-mono text-sm border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-2 py-1"
                  />
                  <input
                    type="text"
                    value="${UI.sanitize(block.title)}"
                    onchange="updateTimeBlock('${block.id}', 'title', this.value)"
                    class="flex-1 border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded px-3 py-2"
                    placeholder="What are you doing?"
                  />
                  <button 
                    onclick="toggleTimeBlockCompletion('${block.id}')"
                    class="w-6 h-6 rounded-full border-2 flex items-center justify-center ${
                      block.completed ? 'bg-green-500 border-green-500' : 'border-slate-300 dark:border-gray-500'
                    }"
                  >
                    ${block.completed ? '<i class="fas fa-check text-white text-xs"></i>' : ''}
                  </button>
                  <button onclick="removeTimeBlock('${block.id}')" class="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg">
                    <i class="fas fa-trash"></i>
                  </button>
                </div>
              `).join('')}
            </div>
          </div>
        </div>

        <div class="grid md:grid-cols-2 gap-6">
          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <h2 class="text-xl font-bold mb-4 dark:text-white">Baseline Goal (X)</h2>
            <p class="text-slate-600 dark:text-gray-300 mb-4">Minimum accomplishment for today</p>
            <textarea
              id="baseline-goal"
              class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg p-3 min-h-[100px]"
              placeholder="What's the minimum you want to achieve today?"
            >${todayPlan.baseline_goal.text}</textarea>
            <div class="flex items-center justify-between mt-4">
              <button onclick="toggleGoalCompletion('baseline')" class="flex items-center gap-2 dark:text-gray-300">
                <div class="w-5 h-5 rounded border flex items-center justify-center ${
                  todayPlan.baseline_goal.completed ? 'bg-green-500 border-green-500' : 'border-slate-300 dark:border-gray-500'
                }">
                  ${todayPlan.baseline_goal.completed ? '<i class="fas fa-check text-white text-xs"></i>' : ''}
                </div>
                <span>${todayPlan.baseline_goal.completed ? 'Completed' : 'Mark as done'}</span>
              </button>
              <button onclick="saveGoals()" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                Save
              </button>
            </div>
          </div>

          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <h2 class="text-xl font-bold mb-4 dark:text-white">Stretch Goal (Y)</h2>
            <p class="text-slate-600 dark:text-gray-300 mb-4">Ambitious target for today</p>
            <textarea
              id="stretch-goal"
              class="w-full border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg p-3 min-h-[100px]"
              placeholder="What would make today amazing?"
            >${todayPlan.stretch_goal.text}</textarea>
            <div class="flex items-center justify-between mt-4">
              <button onclick="toggleGoalCompletion('stretch')" class="flex items-center gap-2 dark:text-gray-300">
                <div class="w-5 h-5 rounded border flex items-center justify-center ${
                  todayPlan.stretch_goal.completed ? 'bg-green-500 border-green-500' : 'border-slate-300 dark:border-gray-500'
                }">
                  ${todayPlan.stretch_goal.completed ? '<i class="fas fa-check text-white text-xs"></i>' : ''}
                </div>
                <span>${todayPlan.stretch_goal.completed ? 'Completed' : 'Mark as done'}</span>
              </button>
              <button onclick="saveGoals()" class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                Save
              </button>
            </div>
          </div>
        </div>

        <!-- 8 Steps to Success -->
        ${(() => {
          const todayDate = stateManager.getTodayDate();
          const eightSteps = state.EightSteps[todayDate] || {};
          const steps = [
            { id: 'positiveAttitude', name: 'Positive Attitude', desc: 'Morning affirmation written', icon: 'fa-smile' },
            { id: 'beOnTime', name: 'Be on Time', desc: 'Left 15 min early', icon: 'fa-clock' },
            { id: 'bePrepared', name: 'Be Prepared', desc: 'Top 3 tasks listed', icon: 'fa-list-check' },
            { id: 'workFullDay', name: 'Work Full Day', desc: '4x 90-min blocks planned', icon: 'fa-briefcase' },
            { id: 'workTerritory', name: 'Work Territory', desc: 'High-impact tasks prioritized', icon: 'fa-bullseye' },
            { id: 'greatAttitude', name: 'Great Attitude', desc: 'Gratitude entry written', icon: 'fa-heart' },
            { id: 'knowWhy', name: 'Know Your Why', desc: 'Purpose for top task', icon: 'fa-lightbulb' },
            { id: 'takeControl', name: 'Take Control', desc: '2-hour focus block scheduled', icon: 'fa-crown' }
          ];
          const completedCount = steps.filter(s => eightSteps[s.id]).length;

          return `
            <div class="rounded-xl border dark:border-gray-700 bg-gradient-to-br from-amber-50 to-orange-50 dark:from-gray-800 dark:to-gray-800 shadow-sm">
              <div class="p-6 border-b border-amber-200 dark:border-gray-700">
                <div class="flex items-center justify-between">
                  <div>
                    <h2 class="text-xl font-bold dark:text-white">8 Steps to Success</h2>
                    <p class="text-sm text-amber-700 dark:text-gray-400 mt-1">SMART goal framework for daily excellence</p>
                  </div>
                  <div class="text-right">
                    <div class="text-2xl font-bold ${completedCount === 8 ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-400'}">${completedCount}/8</div>
                    <p class="text-xs text-amber-700 dark:text-gray-400">Steps Done</p>
                  </div>
                </div>
              </div>
              <div class="p-6">
                <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                  ${steps.map((step, index) => `
                    <button onclick="toggleEightStep('${step.id}')"
                            class="p-3 rounded-lg border-2 transition-all text-left ${
                              eightSteps[step.id]
                                ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                                : 'border-amber-200 dark:border-gray-600 hover:border-amber-400 dark:hover:border-gray-500'
                            }">
                      <div class="flex items-center gap-2 mb-1">
                        <i class="fas ${step.icon} ${eightSteps[step.id] ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-400'}"></i>
                        <span class="text-xs font-bold ${eightSteps[step.id] ? 'text-green-700 dark:text-green-300' : 'text-amber-800 dark:text-gray-300'}">${index + 1}</span>
                      </div>
                      <p class="text-xs font-medium ${eightSteps[step.id] ? 'text-green-700 dark:text-green-300' : 'text-slate-700 dark:text-gray-300'}">${step.name}</p>
                      <p class="text-xs ${eightSteps[step.id] ? 'text-green-600 dark:text-green-400' : 'text-slate-500 dark:text-gray-400'}">${step.desc}</p>
                      ${eightSteps[step.id] ? '<i class="fas fa-check-circle text-green-500 absolute top-2 right-2"></i>' : ''}
                    </button>
                  `).join('')}
                </div>
              </div>
            </div>
          `;
        })()}

        <!-- Contingency Quick Actions -->
        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
          <div class="p-6 border-b dark:border-gray-700">
            <h2 class="text-xl font-bold dark:text-white">Contingency Actions</h2>
            <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Quick adjustments when plans change</p>
          </div>
          <div class="p-6">
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
              <button onclick="activateContingency('runningLate')" class="p-4 rounded-lg border dark:border-gray-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-all text-center">
                <i class="fas fa-running text-2xl text-red-500 mb-2"></i>
                <p class="text-sm font-medium dark:text-gray-300">Running Late</p>
                <p class="text-xs text-slate-500 dark:text-gray-400">Skip non-essentials</p>
              </button>
              <button onclick="activateContingency('lowEnergy')" class="p-4 rounded-lg border dark:border-gray-600 hover:bg-yellow-50 dark:hover:bg-yellow-900/20 transition-all text-center">
                <i class="fas fa-battery-quarter text-2xl text-yellow-500 mb-2"></i>
                <p class="text-sm font-medium dark:text-gray-300">Low Energy</p>
                <p class="text-xs text-slate-500 dark:text-gray-400">Switch to B-Day</p>
              </button>
              <button onclick="activateContingency('freeTime')" class="p-4 rounded-lg border dark:border-gray-600 hover:bg-green-50 dark:hover:bg-green-900/20 transition-all text-center">
                <i class="fas fa-gift text-2xl text-green-500 mb-2"></i>
                <p class="text-sm font-medium dark:text-gray-300">Free Time</p>
                <p class="text-xs text-slate-500 dark:text-gray-400">Quick wins</p>
              </button>
              <button onclick="activateContingency('disruption')" class="p-4 rounded-lg border dark:border-gray-600 hover:bg-purple-50 dark:hover:bg-purple-900/20 transition-all text-center">
                <i class="fas fa-bolt text-2xl text-purple-500 mb-2"></i>
                <p class="text-sm font-medium dark:text-gray-300">Disruption</p>
                <p class="text-xs text-slate-500 dark:text-gray-400">Reassess priorities</p>
              </button>
            </div>
          </div>
        </div>

        ${yesterdayPlan ? `
          <div class="rounded-xl border border-blue-100 dark:border-blue-900 bg-blue-50 dark:bg-blue-900/20 p-6">
            <h3 class="text-lg font-bold text-blue-800 dark:text-blue-300 mb-2">
              <i class="fas fa-history mr-2"></i>Yesterday's Reflection
            </h3>
            <p class="text-blue-700 dark:text-blue-300">You set "${yesterdayPlan.baseline_goal.text}" as your baseline goal.</p>
            ${yesterdayPlan.baseline_goal.completed ?
              '<p class="text-green-700 dark:text-green-400 mt-2"><i class="fas fa-check mr-1"></i>Great job completing it!</p>' :
              '<p class="text-orange-700 dark:text-orange-400 mt-2"><i class="fas fa-lightbulb mr-1"></i>Consider adjusting today\'s goals.</p>'
            }
          </div>
        ` : ''}
      </div>
    `;
  },

  AtoZ() {
    const currentFilter = getAzFilter();
    const currentSearch = getAzSearch();

    const filteredTasks = state.AZTask.filter(task => {
      const matchesStatus = currentFilter === 'all' ||
        (currentFilter === 'completed' && task.status === TASK_STATUS.COMPLETED) ||
        (currentFilter === 'in-progress' && task.status === TASK_STATUS.IN_PROGRESS) ||
        (currentFilter === 'not-started' && task.status === TASK_STATUS.NOT_STARTED);

      const searchLower = currentSearch.toLowerCase();
      const matchesSearch = !currentSearch ||
        task.task.toLowerCase().includes(searchLower) ||
        task.letter.toLowerCase().includes(searchLower) ||
        (task.notes && task.notes.toLowerCase().includes(searchLower));

      return matchesStatus && matchesSearch;
    });

    const stats = {
      total: state.AZTask.length,
      completed: state.AZTask.filter(t => t.status === 'Completed').length,
      inProgress: state.AZTask.filter(t => t.status === 'In Progress').length,
      notStarted: state.AZTask.filter(t => t.status === 'Not Started').length
    };
    
    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <h1 class="text-3xl font-bold tracking-tight dark:text-white">A–Z Tasks</h1>
          <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Plan and track lettered monthly goals</p>
        </div>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          ${[
            { label: 'Total Tasks', value: stats.total, color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' },
            { label: 'Completed', value: stats.completed, color: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' },
            { label: 'In Progress', value: stats.inProgress, color: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300' },
            { label: 'Not Started', value: stats.notStarted, color: 'bg-slate-100 text-slate-700 dark:bg-gray-700 dark:text-gray-300' }
          ].map(stat => `
            <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
              <p class="text-sm text-slate-500 dark:text-gray-400">${stat.label}</p>
              <p class="text-2xl font-bold mt-1 dark:text-white">${stat.value}</p>
              <div class="mt-2 w-full bg-slate-200 dark:bg-gray-700 rounded-full h-2">
                <div class="h-2 rounded-full ${stat.color.split(' ')[0]}" 
                     style="width: ${stats.total ? (stat.value / stats.total) * 100 : 0}%">
                </div>
              </div>
            </div>
          `).join('')}
        </div>

        <div class="flex flex-wrap gap-2 justify-between items-center">
          <div class="flex gap-2">
            <button onclick="openCreateModal()" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              <i class="fas fa-plus mr-2"></i>Add Task
            </button>
            <button onclick="sortTasks()" class="px-4 py-2 border dark:border-gray-600 dark:text-gray-300 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700">
              <i class="fas fa-sort-alpha-down mr-2"></i>Sort
            </button>
          </div>
          <div class="flex gap-2">
            <select onchange="filterTasks(this.value)" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2" aria-label="Filter tasks by status">
              <option value="all" ${currentFilter === 'all' ? 'selected' : ''}>All Tasks</option>
              <option value="completed" ${currentFilter === 'completed' ? 'selected' : ''}>Completed</option>
              <option value="in-progress" ${currentFilter === 'in-progress' ? 'selected' : ''}>In Progress</option>
              <option value="not-started" ${currentFilter === 'not-started' ? 'selected' : ''}>Not Started</option>
            </select>
            <input
              type="text"
              id="az-search-input"
              value="${UI.sanitize(currentSearch)}"
              placeholder="Search tasks..." 
              onkeyup="searchTasks(this.value)"
              class="border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2"
            />
          </div>
        </div>

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
          <div class="p-6">
            ${filteredTasks.length === 0 ? `
              <div class="text-center py-12">
                <i class="fas fa-search text-5xl text-slate-300 dark:text-gray-600 mb-4"></i>
                <h3 class="text-xl font-semibold text-slate-700 dark:text-gray-300 mb-2">No tasks found</h3>
                <p class="text-slate-500 dark:text-gray-400 mb-6">Try adjusting your filters or search query</p>
                ${state.AZTask.length === 0 ? `<button onclick="openCreateModal()" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Create First Task</button>` : ''}
              </div>
            ` : `
              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                ${filteredTasks.map(task => `
                  <div class="border dark:border-gray-700 rounded-xl p-4 hover:shadow-md transition-shadow ${
                    task.status === 'Completed' ? 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800' :
                    task.status === 'In Progress' ? 'bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800' :
                    'bg-white border-slate-200 dark:bg-gray-800 dark:border-gray-700'
                  }">
                    <div class="flex items-start justify-between mb-3">
                      <div class="flex items-center gap-2">
                        <div class="w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg ${
                          task.status === 'Completed' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
                          task.status === 'In Progress' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' :
                          'bg-slate-100 text-slate-700 dark:bg-gray-700 dark:text-gray-300'
                        }">
                          ${task.letter}
                        </div>
                        <span class="font-medium dark:text-gray-300">${UI.sanitize(task.task)}</span>
                      </div>
                      <span class="text-xs px-2 py-1 rounded-full ${
                        task.status === 'Completed' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
                        task.status === 'In Progress' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' :
                        'bg-slate-100 text-slate-700 dark:bg-gray-700 dark:text-gray-300'
                      }">
                        ${UI.sanitize(task.status)}
                      </span>
                    </div>

                    ${task.notes ? `
                      <p class="text-sm text-slate-600 dark:text-gray-400 mb-3">${UI.sanitize(task.notes)}</p>
                    ` : ''}
                    
                    <div class="flex justify-between items-center mt-4">
                      <div class="flex gap-1">
                        <button onclick="completeTask('${task.id}')" class="p-2 hover:bg-green-100 dark:hover:bg-green-900/30 rounded-lg text-green-600 dark:text-green-400">
                          <i class="fas fa-check"></i>
                        </button>
                        <button onclick="openEditModal('${task.id}')" class="p-2 hover:bg-blue-100 dark:hover:bg-blue-900/30 rounded-lg text-blue-600 dark:text-blue-400">
                          <i class="fas fa-edit"></i>
                        </button>
                        <button onclick="deleteTask('${task.id}')" class="p-2 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg text-red-600 dark:text-red-400">
                          <i class="fas fa-trash"></i>
                        </button>
                      </div>
                      <span class="text-xs text-slate-500 dark:text-gray-400">
                        ${new Date(task.createdAt).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                `).join('')}
              </div>
            `}
          </div>
        </div>
      </div>
    `;
  },
  
  WeeklyFocus() {
    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <h1 class="text-3xl font-bold tracking-tight dark:text-white">Weekly Focus Areas</h1>
          <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Balance your efforts across these key areas</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          ${state.FocusArea.map(area => {
            const areaTasks = area.tasks || [];
            const completedTasks = areaTasks.filter(t => t.completed).length;
            const progress = areaTasks.length ? Math.round((completedTasks / areaTasks.length) * 100) : 0;
            
            return `
              <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm hover:shadow-md transition-shadow">
                <div class="flex items-center justify-between mb-4">
                  <h3 class="text-lg font-bold dark:text-white">${UI.sanitize(area.name)}</h3>
                  <div class="w-3 h-3 rounded-full" style="background-color: ${area.color}"></div>
                </div>
                <p class="text-slate-600 dark:text-gray-300 mb-4">${UI.sanitize(area.definition)}</p>
                
                <div class="space-y-2">
                  <div class="flex items-center justify-between text-sm">
                    <span class="text-slate-500 dark:text-gray-400">This Week</span>
                    <span class="font-medium dark:text-gray-300">${completedTasks}/${areaTasks.length} tasks</span>
                  </div>
                  <div class="w-full bg-slate-200 dark:bg-gray-700 rounded-full h-2">
                    <div class="h-2 rounded-full transition-all" style="background-color: ${area.color}; width: ${progress}%"></div>
                  </div>
                </div>
                
                ${areaTasks.length > 0 ? `
                  <div class="mt-4 space-y-2">
                    ${areaTasks.map(task => `
                      <div class="flex items-center gap-2 p-2 rounded-lg bg-slate-50 dark:bg-gray-700">
                        <button onclick="toggleFocusTask('${area.id}', '${task.id}')" class="w-5 h-5 rounded border-2 flex items-center justify-center ${
                          task.completed ? 'bg-green-500 border-green-500' : 'border-slate-300 dark:border-gray-500'
                        }">
                          ${task.completed ? '<i class="fas fa-check text-white text-xs"></i>' : ''}
                        </button>
                        <span class="flex-1 text-sm dark:text-gray-300 ${task.completed ? 'line-through opacity-60' : ''}">${UI.sanitize(task.text)}</span>
                        <button onclick="removeFocusTask('${area.id}', '${task.id}')" class="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded text-red-600 dark:text-red-400">
                          <i class="fas fa-times text-xs"></i>
                        </button>
                      </div>
                    `).join('')}
                  </div>
                ` : ''}
                
                <button onclick="addFocusTask('${area.id}')" class="mt-4 w-full text-center py-2 border dark:border-gray-600 dark:text-gray-300 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700">
                  <i class="fas fa-plus mr-2"></i>Add Task
                </button>
              </div>
            `;
          }).join('')}
        </div>

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
          <h3 class="text-xl font-bold mb-4 dark:text-white">Focus Distribution</h3>
          <p class="text-slate-600 dark:text-gray-300 mb-6">Aim for balanced attention across all areas each week</p>
          
          <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            ${state.FocusArea.map(area => {
              const taskCount = (area.tasks || []).length;
              return `
                <div class="text-center">
                  <div class="w-12 h-12 rounded-full mx-auto mb-2 flex items-center justify-center text-white font-bold" 
                       style="background-color: ${area.color}">
                    ${taskCount}
                  </div>
                  <p class="text-sm font-medium dark:text-gray-300">${UI.sanitize(area.name)}</p>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      </div>
    `;
  },
  
  Routines() {
    const routineTypes = Object.keys(state.Routine);
    const todayPlan = Helpers.getDayPlan();
    if (!todayPlan.routines_completed) todayPlan.routines_completed = {};

    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <div class="flex items-center justify-between">
            <div>
              <h1 class="text-3xl font-bold tracking-tight dark:text-white">Routines</h1>
              <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Build consistency with daily routines</p>
            </div>
            <button onclick="addNewRoutineType()" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              <i class="fas fa-plus mr-2"></i>New Routine
            </button>
          </div>
        </div>

        <!-- Today's Routine Tracker -->
        <div class="rounded-xl border-2 border-blue-200 dark:border-blue-800 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 shadow-sm">
          <div class="p-6 border-b border-blue-200 dark:border-blue-800">
            <div class="flex items-center justify-between">
              <div>
                <h2 class="text-xl font-bold text-blue-900 dark:text-blue-100">Today's Routine Log</h2>
                <p class="text-sm text-blue-700 dark:text-blue-300 mt-1">
                  ${Helpers.formatDate(todayPlan.date)} • Track your daily routine completion
                </p>
              </div>
              <div class="text-right">
                <div class="text-3xl font-bold text-blue-600 dark:text-blue-400">
                  ${Object.values(todayPlan.routines_completed).filter(r => r.completed).length}/${routineTypes.length}
                </div>
                <p class="text-xs text-blue-700 dark:text-blue-300">Routines Done</p>
              </div>
            </div>
          </div>
          <div class="p-6">
            ${routineTypes.length === 0 ? `
              <p class="text-center text-blue-700 dark:text-blue-300 py-8">
                <i class="fas fa-info-circle mb-2"></i><br>
                Create your first routine to start tracking
              </p>
            ` : `
              <div class="grid md:grid-cols-2 gap-4">
                ${routineTypes.map(routineName => {
                  const routine = state.Routine[routineName];
                  const completionData = todayPlan.routines_completed[routineName] || { completed: false, steps: {} };
                  const completedSteps = Object.values(completionData.steps || {}).filter(Boolean).length;
                  const isFullyComplete = completionData.completed;

                  const colorSchemes = {
                    'Morning': { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-700 dark:text-blue-300', icon: 'fa-sun' },
                    'Commute': { bg: 'bg-cyan-100 dark:bg-cyan-900/30', text: 'text-cyan-700 dark:text-cyan-300', icon: 'fa-car' },
                    'Evening': { bg: 'bg-purple-100 dark:bg-purple-900/30', text: 'text-purple-700 dark:text-purple-300', icon: 'fa-moon' },
                    'Afternoon': { bg: 'bg-orange-100 dark:bg-orange-900/30', text: 'text-orange-700 dark:text-orange-300', icon: 'fa-cloud-sun' },
                    'Workout': { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-300', icon: 'fa-dumbbell' },
                    'Work': { bg: 'bg-indigo-100 dark:bg-indigo-900/30', text: 'text-indigo-700 dark:text-indigo-300', icon: 'fa-briefcase' }
                  };
                  const colors = colorSchemes[routineName] || {
                    bg: 'bg-slate-100 dark:bg-gray-700',
                    text: 'text-slate-700 dark:text-gray-300',
                    icon: 'fa-list-check'
                  };

                  return `
                    <div class="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 p-4 ${isFullyComplete ? 'ring-2 ring-green-500' : ''}">
                      <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-2">
                          <i class="fas ${colors.icon} ${colors.text}"></i>
                          <h3 class="font-bold dark:text-white">${UI.sanitize(routineName)}</h3>
                        </div>
                        <button onclick="toggleRoutineComplete('${routineName}')"
                                class="w-8 h-8 rounded-full border-2 flex items-center justify-center transition-all ${
                                  isFullyComplete
                                    ? 'bg-green-500 border-green-500'
                                    : 'border-slate-300 dark:border-gray-500 hover:border-green-500'
                                }">
                          ${isFullyComplete ? '<i class="fas fa-check text-white"></i>' : ''}
                        </button>
                      </div>
                      <div class="space-y-1">
                        ${routine.map((step, index) => {
                          const stepCompleted = completionData.steps?.[index] || false;
                          return `
                            <label class="flex items-center gap-2 p-2 rounded hover:bg-slate-50 dark:hover:bg-gray-700 cursor-pointer group">
                              <input
                                type="checkbox"
                                ${stepCompleted ? 'checked' : ''}
                                onchange="toggleRoutineStep('${routineName}', ${index}, this.checked)"
                                class="w-4 h-4 rounded border-slate-300 dark:border-gray-600 text-green-600 focus:ring-green-500"
                              />
                              <span class="text-sm dark:text-gray-300 flex-1 ${stepCompleted ? 'line-through opacity-60' : ''}">
                                ${UI.sanitize(step)}
                              </span>
                            </label>
                          `;
                        }).join('')}
                      </div>
                      <div class="mt-3 pt-3 border-t dark:border-gray-700">
                        <div class="flex items-center justify-between text-xs">
                          <span class="text-slate-600 dark:text-gray-400">Progress</span>
                          <span class="${completedSteps === routine.length ? 'text-green-600 dark:text-green-400 font-bold' : 'text-slate-600 dark:text-gray-400'}">
                            ${completedSteps}/${routine.length} steps
                          </span>
                        </div>
                        <div class="w-full bg-slate-200 dark:bg-gray-700 rounded-full h-2 mt-2">
                          <div class="bg-green-500 h-2 rounded-full transition-all"
                               style="width: ${routine.length ? (completedSteps / routine.length) * 100 : 0}%"></div>
                        </div>
                      </div>
                    </div>
                  `;
                }).join('')}
              </div>
            `}
          </div>
        </div>

        <div class="grid md:grid-cols-2 gap-6">
          ${routineTypes.map((routineType, typeIndex) => {
            const colorSchemes = {
              'Morning': { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-700 dark:text-blue-300', icon: 'fa-sun' },
              'Commute': { bg: 'bg-cyan-100 dark:bg-cyan-900/30', text: 'text-cyan-700 dark:text-cyan-300', icon: 'fa-car' },
              'Evening': { bg: 'bg-purple-100 dark:bg-purple-900/30', text: 'text-purple-700 dark:text-purple-300', icon: 'fa-moon' },
              'Afternoon': { bg: 'bg-orange-100 dark:bg-orange-900/30', text: 'text-orange-700 dark:text-orange-300', icon: 'fa-cloud-sun' },
              'Workout': { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-300', icon: 'fa-dumbbell' },
              'Work': { bg: 'bg-indigo-100 dark:bg-indigo-900/30', text: 'text-indigo-700 dark:text-indigo-300', icon: 'fa-briefcase' }
            };
            const colors = colorSchemes[routineType] || {
              bg: 'bg-slate-100 dark:bg-gray-700',
              text: 'text-slate-700 dark:text-gray-300',
              icon: 'fa-list-check'
            };

            return `
              <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
                <div class="p-6 border-b dark:border-gray-700">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <i class="fas ${colors.icon} ${colors.text}"></i>
                      <h2 class="text-xl font-bold dark:text-white">${UI.sanitize(routineType)} Routine</h2>
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="px-3 py-1 ${colors.bg} ${colors.text} rounded-full text-sm">
                        ${state.Routine[routineType].length} steps
                      </span>
                      <button onclick="deleteRoutineType('${routineType}')" class="p-2 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg text-red-600 dark:text-red-400">
                        <i class="fas fa-trash text-sm"></i>
                      </button>
                    </div>
                  </div>
                </div>
                <div class="p-6">
                  <div class="space-y-2">
                    ${state.Routine[routineType].map((step, index) => `
                      <div class="flex items-center gap-2 p-2 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700 group">
                        <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button onclick="moveRoutineStep('${routineType}', ${index}, 'up')"
                                  class="p-1 hover:bg-slate-200 dark:hover:bg-gray-600 rounded ${index === 0 ? 'invisible' : ''}"
                                  title="Move up">
                            <i class="fas fa-chevron-up text-xs text-slate-600 dark:text-gray-400"></i>
                          </button>
                          <button onclick="moveRoutineStep('${routineType}', ${index}, 'down')"
                                  class="p-1 hover:bg-slate-200 dark:hover:bg-gray-600 rounded ${index === state.Routine[routineType].length - 1 ? 'invisible' : ''}"
                                  title="Move down">
                            <i class="fas fa-chevron-down text-xs text-slate-600 dark:text-gray-400"></i>
                          </button>
                        </div>
                        <div class="w-7 h-7 rounded-full ${colors.bg} ${colors.text} flex items-center justify-center font-bold text-sm flex-shrink-0">
                          ${index + 1}
                        </div>
                        <input
                          type="text"
                          value="${UI.sanitize(step)}"
                          onchange="updateRoutineStep('${routineType}', ${index}, this.value)"
                          class="flex-1 bg-transparent border-0 dark:text-gray-300 focus:outline-none focus:bg-white dark:focus:bg-gray-700 px-2 py-1 rounded"
                          placeholder="Routine step..."
                        />
                        <button onclick="deleteRoutineStep('${routineType}', ${index})"
                                class="p-1 opacity-0 group-hover:opacity-100 hover:bg-red-100 dark:hover:bg-red-900/30 rounded text-red-600 dark:text-red-400 transition-opacity">
                          <i class="fas fa-times text-sm"></i>
                        </button>
                      </div>
                    `).join('')}

                    <button onclick="addRoutineStep('${routineType}')"
                            class="w-full mt-3 p-3 border-2 border-dashed dark:border-gray-600 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700 ${colors.text} transition-colors">
                      <i class="fas fa-plus mr-2"></i>Add Step
                    </button>
                  </div>
                </div>
              </div>
            `;
          }).join('')}
        </div>

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
          <h3 class="text-xl font-bold mb-4 dark:text-white">Routine Overview</h3>
          <div class="grid md:grid-cols-3 gap-4">
            <div class="text-center p-4">
              <div class="text-3xl font-bold text-blue-600 dark:text-blue-400 mb-1">
                ${Object.values(state.Routine).reduce((sum, routine) => sum + routine.length, 0)}
              </div>
              <p class="text-slate-600 dark:text-gray-300">Total Steps</p>
            </div>
            <div class="text-center p-4">
              <div class="text-3xl font-bold text-green-600 dark:text-green-400 mb-1">
                ${Object.keys(state.Routine).length}
              </div>
              <p class="text-slate-600 dark:text-gray-300">Routines</p>
            </div>
            <div class="text-center p-4">
              <div class="text-3xl font-bold text-purple-600 dark:text-purple-400 mb-1">
                ${Math.round(Object.values(state.Routine).reduce((sum, routine) => sum + routine.length, 0) / Object.keys(state.Routine).length) || 0}
              </div>
              <p class="text-slate-600 dark:text-gray-300">Avg Steps/Routine</p>
            </div>
          </div>
        </div>
      </div>
    `;
  },
  
  Journal() {
    const sortedEntries = [...state.Journal].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <div class="flex items-center justify-between">
            <div>
              <h1 class="text-3xl font-bold tracking-tight dark:text-white">Journal</h1>
              <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Log your thoughts, progress, and reflections</p>
            </div>
            <button onclick="openJournalModal()" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              <i class="fas fa-plus mr-2"></i>New Entry
            </button>
          </div>
        </div>

        ${sortedEntries.length === 0 ? `
          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-12 text-center">
            <i class="fas fa-book text-5xl text-slate-300 dark:text-gray-600 mb-4"></i>
            <h3 class="text-xl font-semibold text-slate-700 dark:text-gray-300 mb-2">No Journal Entries Yet</h3>
            <p class="text-slate-500 dark:text-gray-400 mb-6">Start documenting your journey, wins, and lessons learned</p>
            <button onclick="openJournalModal()" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              Create First Entry
            </button>
          </div>
        ` : `
          <div class="space-y-4">
            ${sortedEntries.map(entry => `
              <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm hover:shadow-md transition-shadow">
                <div class="flex items-start justify-between mb-3">
                  <div class="flex-1">
                    <div class="flex items-center gap-3 mb-2">
                      <h3 class="text-lg font-bold dark:text-white">${entry.title || 'Untitled Entry'}</h3>
                      ${entry.mood ? `<span class="text-2xl">${entry.mood}</span>` : ''}
                    </div>
                    <p class="text-xs text-slate-500 dark:text-gray-400">
                      ${new Date(entry.timestamp).toLocaleString('en-US', { 
                        weekday: 'short', 
                        year: 'numeric', 
                        month: 'short', 
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </p>
                  </div>
                  <div class="flex gap-2">
                    <button onclick="editJournalEntry('${entry.id}')" class="p-2 hover:bg-blue-100 dark:hover:bg-blue-900/30 rounded-lg text-blue-600 dark:text-blue-400">
                      <i class="fas fa-edit"></i>
                    </button>
                    <button onclick="deleteJournalEntry('${entry.id}')" class="p-2 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg text-red-600 dark:text-red-400">
                      <i class="fas fa-trash"></i>
                    </button>
                  </div>
                </div>
                
                ${entry.tags && entry.tags.length > 0 ? `
                  <div class="flex flex-wrap gap-2 mb-3">
                    ${entry.tags.map(tag => `
                      <span class="px-2 py-1 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 rounded-full text-xs">
                        ${tag}
                      </span>
                    `).join('')}
                  </div>
                ` : ''}
                
                <div class="prose dark:prose-invert max-w-none">
                  <p class="text-slate-700 dark:text-gray-300 whitespace-pre-wrap">${entry.content}</p>
                </div>
                
                ${entry.linkedTasks && entry.linkedTasks.length > 0 ? `
                  <div class="mt-4 pt-4 border-t dark:border-gray-700">
                    <p class="text-sm font-medium text-slate-600 dark:text-gray-400 mb-2">Linked Tasks:</p>
                    <div class="flex flex-wrap gap-2">
                      ${entry.linkedTasks.map(taskId => {
                        const task = state.AZTask.find(t => t.id === taskId);
                        return task ? `
                          <span class="px-2 py-1 bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300 rounded text-xs">
                            ${task.letter}: ${task.task}
                          </span>
                        ` : '';
                      }).join('')}
                    </div>
                  </div>
                ` : ''}
              </div>
            `).join('')}
          </div>
        `}
      </div>
    `;
  },

  Reflections() {
    const tabs = [
      { id: 'weekly', label: 'Weekly', icon: 'fa-calendar-week', color: 'blue' },
      { id: 'monthly', label: 'Monthly', icon: 'fa-calendar-alt', color: 'green' },
      { id: 'quarterly', label: 'Quarterly', icon: 'fa-chart-bar', color: 'purple' },
      { id: 'yearly', label: 'Yearly', icon: 'fa-star', color: 'amber' }
    ];

    const activeTab = state.reflectionTab || 'weekly';
    const reflections = state.Reflections[activeTab] || [];
    const sortedReflections = [...reflections].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

    const promptLabels = {
      weekly: { wins: '3 Biggest Wins', challenges: 'Challenges', lessons: 'Lessons Learned', priorities: 'Next Week Priorities' },
      monthly: { accomplishments: 'Accomplishments', goals_progress: 'Goal Progress', improvements: 'Improvements', focus: 'Next Month Focus' },
      quarterly: { milestones: 'Milestones', trends: 'Trends', growth: 'Growth Areas', strategy: 'Strategy' },
      yearly: { top5: 'Top 5 Achievements', transformation: 'Transformation', gratitude: 'Gratitude', vision: 'Vision' }
    };

    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <div class="flex items-center justify-between">
            <div>
              <h1 class="text-3xl font-bold tracking-tight dark:text-white">Reflections</h1>
              <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Review your progress and plan ahead</p>
            </div>
            <button onclick="openReflectionModal('${activeTab}')" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              <i class="fas fa-plus mr-2"></i>New ${activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} Review
            </button>
          </div>
        </div>

        <!-- Tabs -->
        <div class="flex gap-2 border-b dark:border-gray-700 pb-2 overflow-x-auto">
          ${tabs.map(tab => `
            <button onclick="setReflectionTab('${tab.id}')"
                    class="flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${
                      activeTab === tab.id
                        ? `bg-${tab.color}-100 text-${tab.color}-700 dark:bg-${tab.color}-900/30 dark:text-${tab.color}-300 font-medium`
                        : 'text-slate-600 dark:text-gray-400 hover:bg-slate-100 dark:hover:bg-gray-700'
                    }">
              <i class="fas ${tab.icon}"></i>
              <span>${tab.label}</span>
              <span class="ml-1 px-2 py-0.5 rounded-full text-xs ${
                activeTab === tab.id
                  ? `bg-${tab.color}-200 dark:bg-${tab.color}-800`
                  : 'bg-slate-200 dark:bg-gray-600'
              }">${(state.Reflections[tab.id] || []).length}</span>
            </button>
          `).join('')}
        </div>

        <!-- Reflection List -->
        ${sortedReflections.length === 0 ? `
          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-12 text-center">
            <i class="fas fa-lightbulb text-5xl text-slate-300 dark:text-gray-600 mb-4"></i>
            <h3 class="text-xl font-semibold text-slate-700 dark:text-gray-300 mb-2">No ${activeTab} reflections yet</h3>
            <p class="text-slate-500 dark:text-gray-400 mb-6">Take time to review your progress and set intentions</p>
            <button onclick="openReflectionModal('${activeTab}')" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              Start Your First ${activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} Review
            </button>
          </div>
        ` : `
          <div class="space-y-4">
            ${sortedReflections.map(reflection => `
              <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
                <div class="flex items-start justify-between mb-4">
                  <div>
                    <div class="flex items-center gap-2">
                      <span class="text-lg font-bold dark:text-white">
                        ${new Date(reflection.timestamp).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric'
                        })}
                      </span>
                      ${reflection.mood ? `
                        <span class="px-2 py-1 rounded-full text-xs font-medium ${
                          reflection.mood === 'excellent' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
                          reflection.mood === 'good' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' :
                          reflection.mood === 'neutral' ? 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300' :
                          reflection.mood === 'challenging' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300' :
                          'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                        }">${reflection.mood}</span>
                      ` : ''}
                    </div>
                    <p class="text-xs text-slate-500 dark:text-gray-400 mt-1">
                      ${activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} Reflection
                    </p>
                  </div>
                  <button onclick="deleteReflection('${activeTab}', '${reflection.id}')"
                          class="p-2 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg text-red-600 dark:text-red-400">
                    <i class="fas fa-trash"></i>
                  </button>
                </div>

                <div class="space-y-4">
                  ${Object.entries(reflection.responses).map(([key, value]) => `
                    <div class="border-l-4 border-blue-500 pl-4">
                      <h4 class="text-sm font-semibold text-slate-600 dark:text-gray-400 mb-1">
                        ${promptLabels[activeTab][key] || key}
                      </h4>
                      <p class="text-slate-700 dark:text-gray-300 whitespace-pre-wrap">${UI.sanitize(value)}</p>
                    </div>
                  `).join('')}
                </div>
              </div>
            `).join('')}
          </div>
        `}

        <!-- Reflection Summary -->
        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
          <h3 class="text-lg font-bold mb-4 dark:text-white">Reflection Summary</h3>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            ${tabs.map(tab => `
              <div class="text-center p-4 rounded-lg bg-${tab.color}-50 dark:bg-${tab.color}-900/20">
                <div class="text-2xl font-bold text-${tab.color}-600 dark:text-${tab.color}-400 mb-1">
                  ${(state.Reflections[tab.id] || []).length}
                </div>
                <p class="text-sm text-${tab.color}-700 dark:text-${tab.color}-300">${tab.label} Reviews</p>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  },

  Statistics() {
    const az = state.AZTask || [];
    const azDone = az.filter(t => t.status === 'Completed').length;
    const wins = state.MomentumWins || [];
    const today = stateManager.getTodayDate();
    const winsToday = wins.filter(w => w.date === today).length;
    const dayPlans = state.DayPlans || {};
    const plansCount = Object.keys(dayPlans).length;
    const journal = state.Journal || [];
    const reflectionsObj = state.Reflections || {};
    const reflections = Array.isArray(reflectionsObj)
      ? reflectionsObj
      : Object.values(reflectionsObj).flat().filter(Boolean);
    const timeline = (state.History && state.History.timeline) || [];

    const stat = (label, value, color = 'text-blue-400') => `
      <div class="rounded-xl border dark:border-gray-700 bg-gray-900 p-4 shadow-sm">
        <div class="text-xs uppercase tracking-wider text-gray-400 mb-1">${label}</div>
        <div class="text-3xl font-bold ${color}">${value}</div>
      </div>`;

    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <h1 class="text-3xl font-bold tracking-tight dark:text-white">Statistics</h1>
          <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">System activity and usage metrics</p>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          ${stat('A-Z Tasks', az.length)}
          ${stat('A-Z Completed', azDone, 'text-green-400')}
          ${stat('Day Plans', plansCount)}
          ${stat('Wins Today', winsToday, 'text-yellow-400')}
          ${stat('Total Wins', wins.length)}
          ${stat('Journal Entries', journal.length)}
          ${stat('Reflections', reflections.length)}
          ${stat('Timeline Events', timeline.length)}
        </div>
      </div>
    `;
  },

  Timeline() {
    const sortedActivities = (state.History.timeline || [])
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

    // Group by date
    const groupedByDate = {};
    sortedActivities.forEach(activity => {
      const date = new Date(activity.timestamp).toISOString().slice(0, 10);
      if (!groupedByDate[date]) groupedByDate[date] = [];
      groupedByDate[date].push(activity);
    });

    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <div class="flex items-center justify-between">
            <div>
              <h1 class="text-3xl font-bold tracking-tight dark:text-white">Activity Timeline</h1>
              <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Your complete activity history</p>
            </div>
            <button onclick="exportTimeline()" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              <i class="fas fa-download mr-2"></i>Export Timeline
            </button>
          </div>
        </div>

        ${sortedActivities.length === 0 ? `
          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-12 text-center">
            <i class="fas fa-history text-5xl text-slate-300 dark:text-gray-600 mb-4"></i>
            <h3 class="text-xl font-semibold text-slate-700 dark:text-gray-300 mb-2">No Activity Yet</h3>
            <p class="text-slate-500 dark:text-gray-400">Your actions will appear here as you use CycleBoard</p>
          </div>
        ` : `
          <div class="space-y-6">
            ${Object.keys(groupedByDate).map(date => {
              const dateObj = new Date(date);
              const activities = groupedByDate[date];

              return `
                <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
                  <div class="p-4 border-b dark:border-gray-700 bg-slate-50 dark:bg-gray-700/50">
                    <h3 class="font-bold dark:text-white">
                      ${dateObj.toLocaleDateString('en-US', {
                        weekday: 'long',
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric'
                      })}
                    </h3>
                  </div>
                  <div class="p-6">
                    <div class="space-y-4">
                      ${activities.map(activity => {
                        const time = new Date(activity.timestamp).toLocaleTimeString('en-US', {
                          hour: '2-digit',
                          minute: '2-digit'
                        });

                        const iconMap = {
                          'task_created': 'fa-plus-circle text-blue-600 dark:text-blue-400',
                          'task_updated': 'fa-edit text-yellow-600 dark:text-yellow-400',
                          'task_completed': 'fa-check-circle text-green-600 dark:text-green-400',
                          'task_deleted': 'fa-trash text-red-600 dark:text-red-400',
                          'time_block_completed': 'fa-clock text-purple-600 dark:text-purple-400',
                          'focus_task_added': 'fa-bullseye text-indigo-600 dark:text-indigo-400',
                          'focus_task_completed': 'fa-star text-yellow-600 dark:text-yellow-400',
                          'note_added': 'fa-sticky-note text-pink-600 dark:text-pink-400'
                        };

                        const icon = iconMap[activity.type] || 'fa-circle text-slate-600 dark:text-gray-400';

                        return `
                          <div class="flex items-start gap-3">
                            <div class="w-8 h-8 rounded-full bg-slate-100 dark:bg-gray-700 flex items-center justify-center flex-shrink-0 mt-1">
                              <i class="fas ${icon} text-sm"></i>
                            </div>
                            <div class="flex-1 min-w-0">
                              <div class="flex items-baseline gap-2">
                                <span class="text-xs text-slate-500 dark:text-gray-400 font-mono">${time}</span>
                                <p class="text-sm dark:text-gray-300">${UI.sanitize(activity.description)}</p>
                              </div>
                              ${activity.details && Object.keys(activity.details).length > 0 ? `
                                <div class="mt-1 text-xs text-slate-500 dark:text-gray-400">
                                  ${Object.entries(activity.details).map(([key, value]) =>
                                    `<span class="mr-3">${key}: ${UI.sanitize(String(value))}</span>`
                                  ).join('')}
                                </div>
                              ` : ''}
                            </div>
                            <button onclick="deleteActivity('${activity.id}')" class="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded text-red-600 dark:text-red-400 opacity-0 hover:opacity-100 transition-opacity">
                              <i class="fas fa-times text-xs"></i>
                            </button>
                          </div>
                        `;
                      }).join('')}
                    </div>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        `}
      </div>
    `;
  },

  Settings() {
    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <h1 class="text-3xl font-bold tracking-tight dark:text-white">Settings</h1>
          <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Customize your experience</p>
        </div>

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
          <div class="p-6 border-b dark:border-gray-700">
            <h2 class="text-xl font-bold dark:text-white">Preferences</h2>
          </div>
          <div class="p-6 space-y-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium dark:text-gray-300">Dark Mode</p>
                <p class="text-sm text-slate-500 dark:text-gray-400">Switch to dark theme</p>
              </div>
              <button onclick="toggleDarkMode()" class="relative inline-flex h-6 w-11 items-center rounded-full ${
                state.Settings.darkMode ? 'bg-blue-600' : 'bg-slate-300'
              }">
                <span class="inline-block h-4 w-4 transform rounded-full bg-white transition ${
                  state.Settings.darkMode ? 'translate-x-6' : 'translate-x-1'
                }"></span>
              </button>
            </div>
            
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium dark:text-gray-300">Notifications</p>
                <p class="text-sm text-slate-500 dark:text-gray-400">Get reminder notifications</p>
              </div>
              <button onclick="toggleSetting('notifications')" class="relative inline-flex h-6 w-11 items-center rounded-full ${
                state.Settings.notifications ? 'bg-blue-600' : 'bg-slate-300'
              }">
                <span class="inline-block h-4 w-4 transform rounded-full bg-white transition ${
                  state.Settings.notifications ? 'translate-x-6' : 'translate-x-1'
                }"></span>
              </button>
            </div>
            
            <div class="flex items-center justify-between">
              <div>
                <p class="font-medium dark:text-gray-300">Auto-save</p>
                <p class="text-sm text-slate-500 dark:text-gray-400">Automatically save changes</p>
              </div>
              <button onclick="toggleSetting('autoSave')" class="relative inline-flex h-6 w-11 items-center rounded-full ${
                state.Settings.autoSave ? 'bg-blue-600' : 'bg-slate-300'
              }">
                <span class="inline-block h-4 w-4 transform rounded-full bg-white transition ${
                  state.Settings.autoSave ? 'translate-x-6' : 'translate-x-1'
                }"></span>
              </button>
            </div>
            
            <div>
              <label class="font-medium block mb-2 dark:text-gray-300">Default Day Type</label>
              <select onchange="updateSetting('defaultDayType', this.value)" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg px-3 py-2 w-full">
                ${['A', 'B', 'C'].map(type => `
                  <option value="${type}" ${state.Settings.defaultDayType === type ? 'selected' : ''}>
                    ${type} Day ${type === 'A' ? '(Deep Focus)' : type === 'B' ? '(Balanced)' : '(Recovery)'}
                  </option>
                `).join('')}
              </select>
            </div>
          </div>
        </div>

        <!-- Day Type Templates -->
        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
          <div class="p-6 border-b dark:border-gray-700">
            <div class="flex items-center justify-between">
              <div>
                <h2 class="text-xl font-bold dark:text-white">Day Type Templates</h2>
                <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Customize schedules for each day type</p>
              </div>
            </div>
          </div>
          <div class="p-6">
            <div class="grid md:grid-cols-3 gap-4">
              ${['A', 'B', 'C'].map(type => {
                const template = state.DayTypeTemplates?.[type] || {};
                const colors = {
                  A: { bg: 'bg-green-50 dark:bg-green-900/20', border: 'border-green-200 dark:border-green-800', text: 'text-green-700 dark:text-green-300', badge: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300' },
                  B: { bg: 'bg-yellow-50 dark:bg-yellow-900/20', border: 'border-yellow-200 dark:border-yellow-800', text: 'text-yellow-700 dark:text-yellow-300', badge: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300' },
                  C: { bg: 'bg-red-50 dark:bg-red-900/20', border: 'border-red-200 dark:border-red-800', text: 'text-red-700 dark:text-red-300', badge: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' }
                };
                const color = colors[type];

                return `
                  <div class="rounded-xl border ${color.border} ${color.bg} p-4">
                    <div class="flex items-center gap-3 mb-3">
                      <div class="w-10 h-10 rounded-full ${color.badge} flex items-center justify-center text-xl font-bold">
                        ${type}
                      </div>
                      <div>
                        <h3 class="font-bold ${color.text}">${template.name || type + ' Day'}</h3>
                        <p class="text-xs text-slate-500 dark:text-gray-400">${template.description || ''}</p>
                      </div>
                    </div>

                    <div class="space-y-2 text-sm">
                      <div class="flex items-center gap-2 text-slate-600 dark:text-gray-400">
                        <i class="fas fa-clock w-4"></i>
                        <span>${template.timeBlocks?.length || 0} time blocks</span>
                      </div>
                      <div class="flex items-center gap-2 text-slate-600 dark:text-gray-400">
                        <i class="fas fa-list-check w-4"></i>
                        <span>${template.routines?.join(', ') || 'No routines'}</span>
                      </div>
                      <div class="flex items-center gap-2 text-slate-600 dark:text-gray-400">
                        <i class="fas fa-bullseye w-4"></i>
                        <span class="truncate" title="${template.goals?.baseline || ''}">${template.goals?.baseline || 'No baseline'}</span>
                      </div>
                    </div>

                    <button onclick="openDayTypeTemplateEditor('${type}')" class="mt-4 w-full px-3 py-2 border ${color.border} rounded-lg hover:bg-white dark:hover:bg-gray-700 transition text-sm font-medium ${color.text}">
                      <i class="fas fa-edit mr-1"></i> Edit Template
                    </button>
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        </div>

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
          <div class="p-6 border-b dark:border-gray-700">
            <h2 class="text-xl font-bold dark:text-white">Data Management</h2>
          </div>
          <div class="p-6 space-y-4">
            <div class="grid md:grid-cols-2 gap-4">
              <button onclick="exportState()" class="flex items-center gap-3 p-4 border dark:border-gray-600 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700">
                <div class="w-10 h-10 rounded-full bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400 flex items-center justify-center">
                  <i class="fas fa-download"></i>
                </div>
                <div class="text-left">
                  <p class="font-medium dark:text-gray-300">Export Data</p>
                  <p class="text-sm text-slate-500 dark:text-gray-400">Download as JSON file</p>
                </div>
              </button>
              
              <button onclick="showImportModal()" class="flex items-center gap-3 p-4 border dark:border-gray-600 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700">
                <div class="w-10 h-10 rounded-full bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400 flex items-center justify-center">
                  <i class="fas fa-upload"></i>
                </div>
                <div class="text-left">
                  <p class="font-medium dark:text-gray-300">Import Data</p>
                  <p class="text-sm text-slate-500 dark:text-gray-400">Restore from backup</p>
                </div>
              </button>
            </div>
            
            <div class="grid md:grid-cols-2 gap-4">
              <button onclick="clearData()" class="flex items-center gap-3 p-4 border border-red-200 dark:border-red-800 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20">
                <div class="w-10 h-10 rounded-full bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400 flex items-center justify-center">
                  <i class="fas fa-trash-alt"></i>
                </div>
                <div class="text-left">
                  <p class="font-medium text-red-600 dark:text-red-400">Clear All Data</p>
                  <p class="text-sm text-red-500 dark:text-red-400">Permanently delete everything</p>
                </div>
              </button>
              
              <button onclick="resetToDefaults()" class="flex items-center gap-3 p-4 border dark:border-gray-600 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700">
                <div class="w-10 h-10 rounded-full bg-yellow-100 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400 flex items-center justify-center">
                  <i class="fas fa-redo"></i>
                </div>
                <div class="text-left">
                  <p class="font-medium dark:text-gray-300">Reset to Defaults</p>
                  <p class="text-sm text-slate-500 dark:text-gray-400">Restore initial settings</p>
                </div>
              </button>
            </div>
          </div>
        </div>

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
          <div class="p-6 border-b dark:border-gray-700">
            <h2 class="text-xl font-bold dark:text-white">Backup Statistics</h2>
          </div>
          <div class="p-6">
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div class="text-center p-4 bg-slate-50 dark:bg-gray-700/50 rounded-lg">
                <div class="text-2xl font-bold text-green-600 dark:text-green-400 mb-1">
                  ${parseInt(localStorage.getItem('cycleboard-export-count') || '0')}
                </div>
                <p class="text-sm text-slate-600 dark:text-gray-400">Total Exports</p>
              </div>
              <div class="text-center p-4 bg-slate-50 dark:bg-gray-700/50 rounded-lg">
                <div class="text-sm font-medium text-slate-700 dark:text-gray-300 mb-1">
                  ${localStorage.getItem('cycleboard-last-export') ? new Date(localStorage.getItem('cycleboard-last-export')).toLocaleDateString() : 'Never'}
                </div>
                <p class="text-sm text-slate-600 dark:text-gray-400">Last Export</p>
              </div>
              <div class="text-center p-4 bg-slate-50 dark:bg-gray-700/50 rounded-lg">
                <div class="text-sm font-medium text-slate-700 dark:text-gray-300 mb-1">
                  ${localStorage.getItem('cycleboard-last-import') ? new Date(localStorage.getItem('cycleboard-last-import')).toLocaleDateString() : 'Never'}
                </div>
                <p class="text-sm text-slate-600 dark:text-gray-400">Last Import</p>
              </div>
              <div class="text-center p-4 bg-slate-50 dark:bg-gray-700/50 rounded-lg">
                <div class="text-2xl font-bold text-blue-600 dark:text-blue-400 mb-1">
                  ${(JSON.stringify(state).length / 1024).toFixed(1)}
                </div>
                <p class="text-sm text-slate-600 dark:text-gray-400">KB Data Size</p>
              </div>
            </div>
            <div class="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
              <div class="flex items-start gap-2">
                <i class="fas fa-info-circle text-blue-600 dark:text-blue-400 mt-1"></i>
                <div class="text-sm text-blue-800 dark:text-blue-300">
                  <p class="font-medium">Regular backups recommended</p>
                  <p class="text-blue-700 dark:text-blue-400 mt-1">Export your data weekly to prevent data loss. Your data is stored locally in your browser.</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
          <div class="p-6 border-b dark:border-gray-700">
            <h2 class="text-xl font-bold dark:text-white">System Views</h2>
            <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Access other Atlas system interfaces</p>
          </div>
          <div class="p-6 grid grid-cols-1 md:grid-cols-2 gap-3">
            ${[
              { target: 'control', icon: 'fa-sliders-h', color: 'text-indigo-500', label: 'Control Panel', desc: 'System status, loop management' },
              { target: 'atlas', icon: 'fa-project-diagram', color: 'text-violet-500', label: 'Cognitive Atlas', desc: 'Mind-map visualization' },
              { target: 'ideas', icon: 'fa-lightbulb', color: 'text-amber-500', label: 'Idea Dashboard', desc: 'Full idea registry browser' },
              { target: 'docs', icon: 'fa-book', color: 'text-emerald-500', label: 'Docs Viewer', desc: 'System documentation' },
              { target: 'aegis', icon: 'fa-shield-alt', color: 'text-blue-500', label: 'Aegis Dashboard', desc: 'Policy engine admin' },
              { target: 'timeline', icon: 'fa-history', color: 'text-orange-500', label: 'Delta Timeline', desc: 'Event history' },
            ].map(v => `
              <button onclick="AtlasNav.open('${v.target}')" class="flex items-center gap-3 p-4 rounded-lg border dark:border-gray-600 hover:bg-slate-50 dark:hover:bg-gray-700 transition text-left">
                <i class="fas ${v.icon} ${v.color} text-xl w-8"></i>
                <div>
                  <p class="font-medium dark:text-gray-300">${v.label}</p>
                  <p class="text-xs text-slate-500 dark:text-gray-400">${v.desc}</p>
                </div>
                <i class="fas fa-external-link-alt text-slate-300 dark:text-gray-600 ml-auto"></i>
              </button>
            `).join('')}
          </div>
        </div>

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
          <div class="p-6 border-b dark:border-gray-700">
            <h2 class="text-xl font-bold dark:text-white">About CycleBoard</h2>
          </div>
          <div class="p-6 space-y-4">
            <div class="flex items-center gap-3">
              <div class="w-12 h-12 rounded-full bg-gradient-to-r from-blue-500 to-purple-500 flex items-center justify-center text-white">
                <i class="fas fa-sync-alt"></i>
              </div>
              <div>
                <p class="font-medium dark:text-gray-300">in-PACT Self-Sustaining Bullet Journal</p>
                <p class="text-sm text-slate-500 dark:text-gray-400">Version 2.0</p>
              </div>
            </div>
            
            <div class="space-y-2">
              <p class="text-slate-600 dark:text-gray-300">
                CycleBoard helps you plan, execute, and review your monthly goals using the A-Z methodology.
                All data is stored locally in your browser.
              </p>
              <p class="text-sm text-slate-500 dark:text-gray-400">
                Last saved: ${new Date().toLocaleString()}
              </p>
            </div>
            
            <div class="flex gap-2 pt-4">
              <button onclick="navigate('Home')" class="px-4 py-2 bg-slate-100 text-slate-700 dark:bg-gray-700 dark:text-gray-300 rounded-lg hover:bg-slate-200 dark:hover:bg-gray-600">
                <i class="fas fa-question-circle mr-2"></i>Help
              </button>
              <button onclick="exportState()" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                <i class="fas fa-save mr-2"></i>Backup Now
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  },



  // === LIFE DOMAIN SCREENS ===

  Energy() {
    const el = BrainData.getEnergyLevel();
    const ml = BrainData.getMentalLoad();
    const sq = BrainData.energyMetrics?.sleep_quality ?? 3;
    const burnout = BrainData.getBurnoutRisk();
    const redAlert = BrainData.getRedAlertActive();

    const energyColor = el >= 70 ? 'green' : el >= 30 ? 'yellow' : 'red';
    const loadColor = ml <= 3 ? 'green' : ml <= 6 ? 'yellow' : 'red';
    const sleepStars = '\u2605'.repeat(sq) + '\u2606'.repeat(5 - sq);

    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <h1 class="text-3xl font-bold tracking-tight dark:text-white"><i class="fas fa-bolt text-yellow-400 mr-2"></i>Energy</h1>
          <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Physical and mental energy state</p>
        </div>

        ${redAlert ? '<div class="rounded-xl bg-red-900/30 border border-red-700 p-4 text-red-300 text-sm"><i class="fas fa-exclamation-triangle mr-2"></i><strong>RED ALERT ZONE</strong> — Predicted interference window active. Limit to maintenance tasks only.</div>' : ''}
        ${burnout ? '<div class="rounded-xl bg-orange-900/30 border border-orange-700 p-4 text-orange-300 text-sm"><i class="fas fa-fire mr-2"></i><strong>BURNOUT RISK</strong> — Consecutive low-energy days detected. Schedule recovery before execution.</div>' : ''}

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <p class="text-sm text-gray-400">Energy Level</p>
            <p class="text-4xl font-bold mt-2 text-${energyColor}-400">${el}/100</p>
            <div class="w-full bg-gray-700 rounded-full h-3 mt-4">
              <div class="h-3 rounded-full bg-${energyColor}-500 transition-all" style="width: ${el}%"></div>
            </div>
            <p class="text-xs text-gray-500 mt-2">${el >= 70 ? 'Peak — all modes available' : el >= 30 ? 'Moderate — standard execution' : 'Depleted — recovery mode'}</p>
          </div>

          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <p class="text-sm text-gray-400">Mental Load</p>
            <p class="text-4xl font-bold mt-2 text-${loadColor}-400">${ml}/10</p>
            <div class="w-full bg-gray-700 rounded-full h-3 mt-4">
              <div class="h-3 rounded-full bg-${loadColor}-500 transition-all" style="width: ${ml * 10}%"></div>
            </div>
            <p class="text-xs text-gray-500 mt-2">${ml <= 3 ? 'Clear mind — deep work ready' : ml <= 6 ? 'Moderate load — standard tasks' : 'Overloaded — reduce scope'}</p>
          </div>

          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <p class="text-sm text-gray-400">Sleep Quality</p>
            <p class="text-3xl mt-2 text-yellow-400">${sleepStars}</p>
            <p class="text-xs text-gray-500 mt-4">${sq >= 4 ? 'Well rested' : sq >= 3 ? 'Adequate' : 'Poor — prioritize recovery'}</p>
          </div>
        </div>

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
          <h2 class="text-lg font-bold dark:text-white mb-4"><i class="fas fa-sliders-h mr-2 text-blue-400"></i>Update Energy</h2>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label class="text-sm text-gray-400 block mb-1">Energy Level (0-100)</label>
              <input type="range" id="energy-input" min="0" max="100" value="${el}" class="w-full" oninput="document.getElementById('energy-val').textContent=this.value">
              <span id="energy-val" class="text-sm text-gray-300">${el}</span>
            </div>
            <div>
              <label class="text-sm text-gray-400 block mb-1">Mental Load (1-10)</label>
              <input type="range" id="load-input" min="1" max="10" value="${ml}" class="w-full" oninput="document.getElementById('load-val').textContent=this.value">
              <span id="load-val" class="text-sm text-gray-300">${ml}</span>
            </div>
            <div>
              <label class="text-sm text-gray-400 block mb-1">Sleep Quality (1-5)</label>
              <input type="range" id="sleep-input" min="1" max="5" value="${sq}" class="w-full" oninput="document.getElementById('sleep-val').textContent=this.value">
              <span id="sleep-val" class="text-sm text-gray-300">${sq}</span>
            </div>
          </div>
          <button onclick="submitEnergySignals()" class="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition">Save Energy Signals</button>
        </div>
      </div>
    `;
  },

  Finance() {
    const rw = BrainData.getRunwayMonths();
    const income = BrainData.financeMetrics?.monthly_income ?? 0;
    const expenses = BrainData.financeMetrics?.monthly_expenses ?? 0;
    const delta = BrainData.getMoneyDelta();

    const rwColor = rw >= 6 ? 'green' : rw >= 2 ? 'yellow' : 'red';
    const deltaColor = delta >= 0 ? 'green' : 'red';

    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <h1 class="text-3xl font-bold tracking-tight dark:text-white"><i class="fas fa-wallet text-emerald-400 mr-2"></i>Finance</h1>
          <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Financial position and resource tracking</p>
        </div>

        ${rw < 2 ? '<div class="rounded-xl bg-red-900/30 border border-red-700 p-4 text-red-300 text-sm"><i class="fas fa-exclamation-triangle mr-2"></i><strong>FINANCIAL CONSTRAINT</strong> — Runway under 2 months. System will enforce CLOSURE mode until stabilized.</div>' : ''}

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <p class="text-sm text-gray-400">Runway</p>
            <p class="text-4xl font-bold mt-2 text-${rwColor}-400">${rw.toFixed(1)} mo</p>
            <p class="text-xs text-gray-500 mt-2">${rw >= 6 ? 'Secure — growth unlocked' : rw >= 2 ? 'Moderate — build carefully' : 'Critical — ship revenue work'}</p>
          </div>

          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <p class="text-sm text-gray-400">Monthly Net</p>
            <p class="text-4xl font-bold mt-2 text-${deltaColor}-400">${delta >= 0 ? '+' : ''}$${Math.abs(delta).toLocaleString()}</p>
            <p class="text-xs text-gray-500 mt-2">Income: $${income.toLocaleString()} | Expenses: $${expenses.toLocaleString()}</p>
          </div>

          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <p class="text-sm text-gray-400">Routing Impact</p>
            <p class="text-lg font-bold mt-2 dark:text-white">${rw < 2 ? 'CLOSURE enforced' : rw >= 6 ? 'No constraints' : 'Standard routing'}</p>
            <p class="text-xs text-gray-500 mt-2">Financial position feeds into mode routing as a constraint signal</p>
          </div>
        </div>

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
          <h2 class="text-lg font-bold dark:text-white mb-4"><i class="fas fa-edit mr-2 text-blue-400"></i>Update Finance</h2>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label class="text-sm text-gray-400 block mb-1">Runway (months)</label>
              <input type="number" id="runway-input" value="${rw}" min="0" step="0.5" class="w-full bg-gray-700 border-gray-600 rounded-lg px-3 py-2 text-white">
            </div>
            <div>
              <label class="text-sm text-gray-400 block mb-1">Monthly Income ($)</label>
              <input type="number" id="income-input" value="${income}" min="0" class="w-full bg-gray-700 border-gray-600 rounded-lg px-3 py-2 text-white">
            </div>
            <div>
              <label class="text-sm text-gray-400 block mb-1">Monthly Expenses ($)</label>
              <input type="number" id="expenses-input" value="${expenses}" min="0" class="w-full bg-gray-700 border-gray-600 rounded-lg px-3 py-2 text-white">
            </div>
          </div>
          <button onclick="submitFinanceSignals()" class="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition">Save Finance Signals</button>
        </div>
      </div>
    `;
  },

  Skills() {
    const util = BrainData.getSkillsUtilization();
    const learning = BrainData.skillsMetrics?.active_learning ?? false;
    const mastery = BrainData.skillsMetrics?.mastery_count ?? 0;
    const growth = BrainData.skillsMetrics?.growth_count ?? 0;

    const utilColor = util >= 70 ? 'green' : util >= 40 ? 'yellow' : 'red';

    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <h1 class="text-3xl font-bold tracking-tight dark:text-white"><i class="fas fa-graduation-cap text-purple-400 mr-2"></i>Skills</h1>
          <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Skill utilization and mastery tracking</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <p class="text-sm text-gray-400">Utilization</p>
            <p class="text-4xl font-bold mt-2 text-${utilColor}-400">${Math.round(util)}%</p>
            <div class="w-full bg-gray-700 rounded-full h-3 mt-4">
              <div class="h-3 rounded-full bg-${utilColor}-500 transition-all" style="width: ${util}%"></div>
            </div>
            <p class="text-xs text-gray-500 mt-2">${util >= 70 ? 'Leveraging strengths' : util >= 40 ? 'Mixed alignment' : 'Working in weakness areas'}</p>
          </div>

          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm text-center">
            <p class="text-sm text-gray-400">Active Learning</p>
            <p class="text-4xl mt-2">${learning ? '<i class="fas fa-check-circle text-green-400"></i>' : '<i class="fas fa-times-circle text-gray-600"></i>'}</p>
            <p class="text-xs text-gray-500 mt-2">${learning ? 'Practicing this week' : 'No active practice'}</p>
          </div>

          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm text-center">
            <p class="text-sm text-gray-400">Mastered</p>
            <p class="text-4xl font-bold mt-2 text-blue-400">${mastery}</p>
            <p class="text-xs text-gray-500 mt-2">Skills at mastery level</p>
          </div>

          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm text-center">
            <p class="text-sm text-gray-400">Growing</p>
            <p class="text-4xl font-bold mt-2 text-cyan-400">${growth}</p>
            <p class="text-xs text-gray-500 mt-2">Skills in development</p>
          </div>
        </div>

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
          <h2 class="text-lg font-bold dark:text-white mb-4"><i class="fas fa-edit mr-2 text-blue-400"></i>Update Skills</h2>
          <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label class="text-sm text-gray-400 block mb-1">Utilization % (0-100)</label>
              <input type="range" id="util-input" min="0" max="100" value="${Math.round(util)}" class="w-full" oninput="document.getElementById('util-val').textContent=this.value+'%'">
              <span id="util-val" class="text-sm text-gray-300">${Math.round(util)}%</span>
            </div>
            <div>
              <label class="text-sm text-gray-400 block mb-1">Active Learning</label>
              <select id="learning-input" class="w-full bg-gray-700 border-gray-600 rounded-lg px-3 py-2 text-white">
                <option value="true" ${learning ? 'selected' : ''}>Yes</option>
                <option value="false" ${!learning ? 'selected' : ''}>No</option>
              </select>
            </div>
            <div>
              <label class="text-sm text-gray-400 block mb-1">Mastery Count</label>
              <input type="number" id="mastery-input" value="${mastery}" min="0" class="w-full bg-gray-700 border-gray-600 rounded-lg px-3 py-2 text-white">
            </div>
            <div>
              <label class="text-sm text-gray-400 block mb-1">Growth Count</label>
              <input type="number" id="growth-input" value="${growth}" min="0" class="w-full bg-gray-700 border-gray-600 rounded-lg px-3 py-2 text-white">
            </div>
          </div>
          <button onclick="submitSkillsSignals()" class="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition">Save Skills Signals</button>
        </div>
      </div>
    `;
  },

  Network() {
    const score = BrainData.getNetworkScore();
    const active = BrainData.networkMetrics?.active_relationships ?? 0;
    const outreach = BrainData.networkMetrics?.outreach_this_week ?? 0;

    const scoreColor = score >= 60 ? 'green' : score >= 20 ? 'yellow' : 'red';

    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <h1 class="text-3xl font-bold tracking-tight dark:text-white"><i class="fas fa-users text-blue-400 mr-2"></i>Network</h1>
          <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">Relationship and collaboration tracking</p>
        </div>

        ${score < 20 ? '<div class="rounded-xl bg-yellow-900/30 border border-yellow-700 p-4 text-yellow-300 text-sm"><i class="fas fa-info-circle mr-2"></i><strong>ISOLATION DETECTED</strong> — Network score below 20. SCALE mode unavailable until collaboration infrastructure improves.</div>' : ''}

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <p class="text-sm text-gray-400">Collaboration Score</p>
            <p class="text-4xl font-bold mt-2 text-${scoreColor}-400">${score}/100</p>
            <div class="w-full bg-gray-700 rounded-full h-3 mt-4">
              <div class="h-3 rounded-full bg-${scoreColor}-500 transition-all" style="width: ${score}%"></div>
            </div>
            <p class="text-xs text-gray-500 mt-2">${score >= 60 ? 'Well-connected' : score >= 20 ? 'Building network' : 'Isolated — outreach needed'}</p>
          </div>

          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm text-center">
            <p class="text-sm text-gray-400">Active Relationships</p>
            <p class="text-4xl font-bold mt-2 text-blue-400">${active}</p>
            <p class="text-xs text-gray-500 mt-2">Interactions in last 30 days</p>
          </div>

          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm text-center">
            <p class="text-sm text-gray-400">Outreach This Week</p>
            <p class="text-4xl font-bold mt-2 text-cyan-400">${outreach}</p>
            <p class="text-xs text-gray-500 mt-2">Proactive connections made</p>
          </div>
        </div>

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
          <h2 class="text-lg font-bold dark:text-white mb-4"><i class="fas fa-edit mr-2 text-blue-400"></i>Update Network</h2>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label class="text-sm text-gray-400 block mb-1">Collaboration Score (0-100)</label>
              <input type="range" id="collab-input" min="0" max="100" value="${score}" class="w-full" oninput="document.getElementById('collab-val').textContent=this.value">
              <span id="collab-val" class="text-sm text-gray-300">${score}</span>
            </div>
            <div>
              <label class="text-sm text-gray-400 block mb-1">Active Relationships</label>
              <input type="number" id="active-input" value="${active}" min="0" class="w-full bg-gray-700 border-gray-600 rounded-lg px-3 py-2 text-white">
            </div>
            <div>
              <label class="text-sm text-gray-400 block mb-1">Outreach This Week</label>
              <input type="number" id="outreach-input" value="${outreach}" min="0" class="w-full bg-gray-700 border-gray-600 rounded-lg px-3 py-2 text-white">
            </div>
          </div>
          <button onclick="submitNetworkSignals()" class="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition">Save Network Signals</button>
        </div>
      </div>
    `;
  },

  OSINT() {
    const feed = BrainData.osintFeed || {};
    const status = feed.status || 'unknown';
    const highlights = feed.highlights || [];
    const economic = feed.economic || [];
    const market = feed.market || {};
    const risks = feed.risks || [];
    const freshness = feed.generated_at ? DataFreshness.check(feed.generated_at, 1) : { ageText: 'never', stale: true };

    const statusColor = status === 'online' ? 'green' : status === 'offline' ? 'red' : 'gray';

    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <div class="flex items-center justify-between">
            <div>
              <h1 class="text-3xl font-bold tracking-tight dark:text-white"><i class="fas fa-satellite-dish text-cyan-400 mr-2"></i>OSINT</h1>
              <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">External intelligence from Crucix (27 sources)</p>
            </div>
            <div class="text-right">
              <span class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-${statusColor}-900/30 text-${statusColor}-400">
                <span class="w-2 h-2 rounded-full bg-${statusColor}-400"></span>
                ${status === 'online' ? 'Crucix Online' : status === 'offline' ? 'Crucix Offline' : 'No Data'}
              </span>
              <p class="text-[10px] text-gray-500 mt-1">Updated ${freshness.ageText}</p>
            </div>
          </div>
        </div>

        ${highlights.length > 0 ? `
          <div class="rounded-xl border dark:border-gray-700 bg-gray-900 p-6 shadow-sm">
            <h2 class="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3"><i class="fas fa-bolt text-yellow-400 mr-1"></i>Highlights</h2>
            <div class="space-y-2">
              ${highlights.map(h => `
                <div class="flex items-start gap-2 text-sm text-gray-300">
                  <i class="fas fa-chevron-right text-cyan-500 mt-1 text-xs"></i>
                  <span>${typeof UI !== 'undefined' ? UI.sanitize(h) : h}</span>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          ${(() => {
            const indexes = market.indexes || [];
            const crypto = market.crypto || [];
            const vix = market.vix;
            const allQuotes = [...indexes, ...crypto].slice(0, 6);
            const hasMarket = allQuotes.length > 0 || vix;
            return `
            <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
              <h2 class="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3"><i class="fas fa-chart-line text-green-400 mr-1"></i>Markets</h2>
              ${hasMarket ? `
                <div class="space-y-2">
                  ${allQuotes.map(q => {
                    const pct = q.changePct;
                    const color = pct > 0 ? 'text-green-400' : pct < 0 ? 'text-red-400' : 'text-gray-300';
                    const arrow = pct > 0 ? '▲' : pct < 0 ? '▼' : '';
                    return `
                    <div class="flex items-center justify-between text-sm">
                      <div>
                        <span class="text-gray-400 font-mono">${q.symbol || '?'}</span>
                        <span class="text-[10px] text-gray-600 ml-1">${(q.name || '').substring(0, 15)}</span>
                      </div>
                      <div class="text-right">
                        <span class="font-bold text-gray-200">$${typeof q.price === 'number' ? q.price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) : q.price}</span>
                        ${pct != null ? `<span class="text-xs ${color} ml-2">${arrow} ${Math.abs(pct).toFixed(1)}%</span>` : ''}
                      </div>
                    </div>`;
                  }).join('')}
                  ${vix ? `
                    <div class="flex items-center justify-between text-sm border-t border-gray-700 pt-2 mt-2">
                      <span class="text-gray-400 font-mono">VIX</span>
                      <span class="font-bold ${vix.value >= 25 ? 'text-red-400' : vix.value >= 18 ? 'text-yellow-400' : 'text-green-400'}">${vix.value?.toFixed(1) || '?'}</span>
                    </div>
                  ` : ''}
                  ${market.gold ? `
                    <div class="flex items-center justify-between text-sm">
                      <span class="text-gray-400 font-mono">GOLD</span>
                      <div class="text-right">
                        <span class="font-bold text-yellow-400">$${market.gold.toLocaleString()}</span>
                        ${market.gold_change_pct != null ? `<span class="text-xs text-gray-400 ml-2">${market.gold_change_pct > 0 ? '+' : ''}${market.gold_change_pct.toFixed(1)}%</span>` : ''}
                      </div>
                    </div>
                  ` : ''}
                </div>
              ` : '<p class="text-sm text-gray-500">No market data available</p>'}
            </div>`;
          })()}

          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <h2 class="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3"><i class="fas fa-newspaper text-cyan-400 mr-1"></i>News</h2>
            ${(() => {
              const news = feed.news || [];
              return news.length > 0 ? `
                <div class="space-y-2">
                  ${news.slice(0, 6).map(n => `
                    <div class="text-sm">
                      <div class="flex items-start gap-1">
                        ${n.urgent ? '<span class="text-red-400 text-[10px]">URGENT</span>' : ''}
                        <p class="text-gray-300">${typeof UI !== 'undefined' ? UI.sanitize(n.headline) : n.headline}</p>
                      </div>
                      <span class="text-[10px] text-gray-600">${typeof UI !== 'undefined' ? UI.sanitize(n.source || '') : n.source || ''}</span>
                    </div>
                  `).join('')}
                </div>
              ` : '<p class="text-sm text-gray-500">No news headlines available</p>';
            })()}
          </div>
        </div>

        ${economic.length > 0 ? `
          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <h2 class="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3"><i class="fas fa-landmark text-blue-400 mr-1"></i>Economic Indicators</h2>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
              ${economic.slice(0, 8).map(e => {
                const mom = e.mom_change_pct;
                const momColor = mom > 0 ? 'text-green-400' : mom < 0 ? 'text-red-400' : 'text-gray-500';
                return `
                <div class="text-center p-3 bg-gray-700/30 rounded-lg">
                  <p class="text-[10px] text-gray-500 uppercase">${typeof UI !== 'undefined' ? UI.sanitize(e.indicator || '') : e.indicator || ''}</p>
                  <p class="text-lg font-bold text-gray-200 mt-1">${e.value != null ? e.value : '?'}</p>
                  ${mom != null ? `<p class="text-[10px] ${momColor}">${mom > 0 ? '+' : ''}${mom.toFixed(1)}% MoM</p>` : `<p class="text-[10px] text-gray-600">${typeof UI !== 'undefined' ? UI.sanitize(e.source || '') : e.source || ''}</p>`}
                </div>`;
              }).join('')}
            </div>
          </div>
        ` : ''}

        ${status === 'offline' ? `
          <div class="rounded-xl border border-dashed dark:border-gray-600 p-6 text-center">
            <i class="fas fa-plug text-4xl text-gray-600 mb-3"></i>
            <p class="text-gray-400">Crucix is offline. Start it with: <code class="text-cyan-400">node server.mjs</code> in the Crucix directory (port 3117)</p>
            <p class="text-xs text-gray-500 mt-2">Atlas governance continues without OSINT data</p>
          </div>
        ` : ''}
      </div>
    `;
  }
};

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { screens, renderNav, navigate, ScreenRenderers };
}
