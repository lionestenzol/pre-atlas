// Atlas Dashboard Screens Module
// Navigation and Screen Renderers
const screens = [
  { id: 'Command', label: 'Command', icon: 'fa-terminal' },
  { id: 'Home', label: 'Home', icon: 'fa-home' },
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
