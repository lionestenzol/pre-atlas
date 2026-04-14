// inPACT Screens Module
// Navigation and Screen Renderers
const screens = [
  { id: 'Home', label: 'Home', icon: 'fa-home' },
  { id: 'Daily', label: 'Daily', icon: 'fa-calendar-day' },
  { id: 'Calendar', label: 'Calendar', icon: 'fa-calendar-alt' },
  { id: 'AtoZ', label: 'A–Z', icon: 'fa-tasks' },
  { id: 'WeeklyFocus', label: 'Weekly Focus', icon: 'fa-bullseye' },
  { id: 'Routines', label: 'Routines', icon: 'fa-clock' },
  { id: 'Journal', label: 'Journal', icon: 'fa-book' },
  { id: 'Reflections', label: 'Reflections', icon: 'fa-lightbulb' },
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
  `).join('');
  
  const weeklyStats = Helpers.getWeeklyStats();
  const weeklyTasksEl = document.getElementById('weekly-tasks');
  const weeklyProgressBarEl = document.getElementById('weekly-progress-bar');
  if (weeklyTasksEl) weeklyTasksEl.textContent = `${weeklyStats.completed}/${weeklyStats.total}`;
  if (weeklyProgressBarEl) weeklyProgressBarEl.style.width = `${weeklyStats.percentage}%`;
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
    const completionPct = Helpers.calculateCompletionPercentage();
    const weeklyStats = Helpers.getWeeklyStats();
    const todayPlan = Helpers.getDayPlan();
    
    return `
      <div class="space-y-6 fade-in">
        <div class="mb-6">
          <h1 class="text-3xl font-bold tracking-tight dark:text-white">Welcome Back!</h1>
          <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">${Helpers.formatDate(stateManager.getTodayDate())} • Ready to make today productive?</p>
        </div>


        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-slate-500 dark:text-gray-400">A–Z Completion</p>
                <p class="text-2xl font-bold mt-1 dark:text-white">${completionPct}%</p>
              </div>
              <div>${UI.renderProgressRing(completionPct)}</div>
            </div>
            <div class="mt-4 text-sm text-slate-600 dark:text-gray-300">
              ${state.AZTask.filter(t => t.status === 'Completed').length} of ${state.AZTask.length} tasks done
            </div>
          </div>

          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-slate-500 dark:text-gray-400">Weekly Progress</p>
                <p class="text-2xl font-bold mt-1 dark:text-white">${weeklyStats.percentage}%</p>
              </div>
              <i class="fas fa-chart-line text-2xl text-blue-500"></i>
            </div>
            <div class="mt-4 text-sm text-slate-600 dark:text-gray-300">
              ${weeklyStats.completed} of ${weeklyStats.total} days met baseline
            </div>
          </div>

          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-slate-500 dark:text-gray-400">Today's Focus</p>
                <p class="text-2xl font-bold mt-1 dark:text-white">${todayPlan.day_type} Day</p>
              </div>
              <span class="text-2xl font-bold ${todayPlan.day_type === 'A' ? 'text-blue-600 dark:text-blue-400' : todayPlan.day_type === 'B' ? 'text-green-600 dark:text-green-400' : 'text-purple-600 dark:text-purple-400'}">
                ${todayPlan.day_type}
              </span>
            </div>
            <div class="mt-4">
              <button onclick="navigate('Daily')" class="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 font-medium">
                View daily plan →
              </button>
            </div>
          </div>
        </div>

        ${(() => {
          const dailyProgress = Helpers.calculateDailyProgress();
          return `
            <div class="rounded-xl border dark:border-gray-700 bg-gradient-to-br from-blue-50 to-purple-50 dark:from-gray-800 dark:to-gray-800 p-6 shadow-sm">
              <div class="flex items-center justify-between mb-4">
                <div>
                  <h2 class="text-xl font-bold dark:text-white">Today's Progress</h2>
                  <p class="text-sm text-slate-600 dark:text-gray-400">Track your daily completion</p>
                </div>
                <div class="text-right">
                  <div class="text-4xl font-bold ${
                    dailyProgress.overall >= 80 ? 'text-green-600 dark:text-green-400' :
                    dailyProgress.overall >= 50 ? 'text-blue-600 dark:text-blue-400' :
                    dailyProgress.overall >= 25 ? 'text-yellow-600 dark:text-yellow-400' :
                    'text-slate-400 dark:text-gray-500'
                  }">${dailyProgress.overall}%</div>
                  <p class="text-xs text-slate-500 dark:text-gray-400 mt-1">Overall</p>
                </div>
              </div>

              <div class="w-full bg-slate-200 dark:bg-gray-700 rounded-full h-3 mb-6">
                <div class="h-3 rounded-full transition-all ${
                  dailyProgress.overall >= 80 ? 'bg-gradient-to-r from-green-500 to-emerald-500' :
                  dailyProgress.overall >= 50 ? 'bg-gradient-to-r from-blue-500 to-cyan-500' :
                  dailyProgress.overall >= 25 ? 'bg-gradient-to-r from-yellow-500 to-orange-500' :
                  'bg-gradient-to-r from-slate-400 to-slate-500'
                }" style="width: ${dailyProgress.overall}%"></div>
              </div>

              <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                ${dailyProgress.breakdown.map(item => `
                  <div class="text-center p-3 bg-white dark:bg-gray-700/50 rounded-lg">
                    <i class="fas ${item.icon} ${UI.getColorClass(item.color, 'text')} ${UI.getColorClass(item.color, 'textDark')} text-lg mb-2"></i>
                    <p class="text-xs text-slate-600 dark:text-gray-400 mb-1">${item.label}</p>
                    <p class="text-lg font-bold dark:text-white">${item.percentage}%</p>
                    <p class="text-xs text-slate-500 dark:text-gray-500">${item.completed}/${item.total}</p>
                    <div class="w-full bg-slate-200 dark:bg-gray-600 rounded-full h-1.5 mt-2">
                      <div class="${UI.getColorClass(item.color, 'bg')} h-1.5 rounded-full transition-all" style="width: ${item.percentage}%"></div>
                    </div>
                  </div>
                `).join('')}
              </div>
            </div>
          `;
        })()}


        

        

        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <button onclick="openCreateModal()" class="rounded-lg border dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center hover:bg-slate-50 dark:hover:bg-gray-700 transition-colors">
            <i class="fas fa-plus-circle text-blue-500 text-xl mb-2"></i>
            <p class="text-sm font-medium dark:text-gray-300">Add Task</p>
          </button>
          <button onclick="navigate('Daily')" class="rounded-lg border dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center hover:bg-slate-50 dark:hover:bg-gray-700 transition-colors">
            <i class="fas fa-edit text-green-500 text-xl mb-2"></i>
            <p class="text-sm font-medium dark:text-gray-300">Plan Day</p>
          </button>
          <button onclick="completeAllTodayTasks()" class="rounded-lg border dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center hover:bg-slate-50 dark:hover:bg-gray-700 transition-colors">
            <i class="fas fa-check-double text-purple-500 text-xl mb-2"></i>
            <p class="text-sm font-medium dark:text-gray-300">Complete All</p>
          </button>
          <button onclick="navigate('Settings')" class="rounded-lg border dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center hover:bg-slate-50 dark:hover:bg-gray-700 transition-colors">
            <i class="fas fa-chart-bar text-yellow-500 text-xl mb-2"></i>
            <p class="text-sm font-medium dark:text-gray-300">Statistics</p>
          </button>
        </div>

        ${(() => {
          const streak = Helpers.getProgressStreak();
          const history = Helpers.getProgressHistory(7);
          const avgProgress = Helpers.getAverageProgress(7);

          return `
            <div class="grid md:grid-cols-2 gap-4">
              <!-- Streak Tracker -->
              <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
                <div class="flex items-center justify-between mb-4">
                  <h2 class="text-lg font-bold dark:text-white">Productivity Streak</h2>
                  <i class="fas fa-fire text-2xl ${streak > 0 ? 'text-orange-500' : 'text-slate-300 dark:text-gray-600'}"></i>
                </div>
                <div class="text-center mb-4">
                  <div class="text-5xl font-bold ${streak > 0 ? 'text-orange-500' : 'text-slate-400 dark:text-gray-500'} mb-2">${streak}</div>
                  <p class="text-sm text-slate-600 dark:text-gray-400">${streak === 1 ? 'day' : 'days'} with 70%+ progress</p>
                </div>
                ${streak > 0 ? `
                  <div class="text-center p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg">
                    <p class="text-sm font-medium ${
                      streak >= 7 ? 'text-orange-700 dark:text-orange-300' : 'text-orange-600 dark:text-orange-400'
                    }">
                      ${streak >= 30 ? '🔥 Legendary! Keep it going!' :
                        streak >= 14 ? '💪 Outstanding streak!' :
                        streak >= 7 ? '⚡ One week strong!' :
                        '🌟 Great momentum!'}
                    </p>
                  </div>
                ` : `
                  <div class="text-center p-3 bg-slate-50 dark:bg-gray-700/50 rounded-lg">
                    <p class="text-sm text-slate-600 dark:text-gray-400">Complete today at 70%+ to start your streak!</p>
                  </div>
                `}
              </div>

              <!-- 7-Day Progress History -->
              <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
                <div class="flex items-center justify-between mb-4">
                  <h2 class="text-lg font-bold dark:text-white">7-Day Overview</h2>
                  <span class="text-sm font-medium ${
                    avgProgress >= 70 ? 'text-green-600 dark:text-green-400' :
                    avgProgress >= 50 ? 'text-blue-600 dark:text-blue-400' :
                    'text-slate-500 dark:text-gray-400'
                  }">${avgProgress}% avg</span>
                </div>
                <div class="space-y-2">
                  ${history.map(day => `
                    <div class="flex items-center gap-3">
                      <span class="text-xs text-slate-500 dark:text-gray-400 w-16">${day.dateFormatted.split(',')[0]}</span>
                      <div class="flex-1 bg-slate-200 dark:bg-gray-700 rounded-full h-6 relative overflow-hidden">
                        <div class="${
                          day.progress >= 80 ? 'bg-green-500' :
                          day.progress >= 70 ? 'bg-blue-500' :
                          day.progress >= 50 ? 'bg-yellow-500' :
                          day.progress > 0 ? 'bg-slate-400' :
                          'bg-slate-200 dark:bg-gray-700'
                        } h-6 rounded-full transition-all flex items-center justify-end pr-2"
                             style="width: ${day.progress}%">
                          ${day.progress > 15 ? `<span class="text-xs font-medium text-white">${day.progress}%</span>` : ''}
                        </div>
                        ${day.progress <= 15 && day.progress > 0 ? `
                          <span class="absolute right-2 top-1 text-xs font-medium text-slate-600 dark:text-gray-300">${day.progress}%</span>
                        ` : ''}
                        ${!day.hasData ? `
                          <span class="absolute inset-0 flex items-center justify-center text-xs text-slate-400 dark:text-gray-500">No data</span>
                        ` : ''}
                      </div>
                      ${day.progress >= 70 ? '<i class="fas fa-check-circle text-green-500 text-sm"></i>' : '<div class="w-4"></div>'}
                    </div>
                  `).join('')}
                </div>
              </div>
            </div>
          `;
        })()}

        ${Object.keys(state.Routine).length > 0 ? `
          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
            <div class="p-6 border-b dark:border-gray-700">
              <div class="flex items-center justify-between">
                <h2 class="text-xl font-bold dark:text-white">Today's Routines</h2>
                <button onclick="navigate('Routines')" class="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300">
                  View All →
                </button>
              </div>
            </div>
            <div class="p-6">
              <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
                ${Object.keys(state.Routine).map(routineName => {
                  const routine = state.Routine[routineName];
                  const completionData = todayPlan.routines_completed?.[routineName] || { completed: false, steps: {} };
                  const completedSteps = Object.values(completionData.steps || {}).filter(Boolean).length;
                  const isComplete = completionData.completed;

                  const colorSchemes = {
                    'Morning': 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
                    'Commute': 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-300',
                    'Evening': 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
                    'Afternoon': 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
                    'Workout': 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
                    'Work': 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300'
                  };
                  const colors = colorSchemes[routineName] || 'bg-slate-100 text-slate-700 dark:bg-gray-700 dark:text-gray-300';

                  return `
                    <button onclick="navigate('Routines')"
                            class="p-4 rounded-lg border dark:border-gray-700 hover:shadow-md transition-all text-left ${isComplete ? 'ring-2 ring-green-500' : ''}">
                      <div class="flex items-center justify-between mb-2">
                        <span class="px-2 py-1 ${colors} rounded-full text-xs font-medium">
                          ${UI.sanitize(routineName)}
                        </span>
                        ${isComplete ? '<i class="fas fa-check-circle text-green-500"></i>' : ''}
                      </div>
                      <div class="text-sm text-slate-600 dark:text-gray-400 mb-2">
                        ${completedSteps}/${routine.length} steps
                      </div>
                      <div class="w-full bg-slate-200 dark:bg-gray-700 rounded-full h-1.5">
                        <div class="bg-green-500 h-1.5 rounded-full transition-all"
                             style="width: ${routine.length ? (completedSteps / routine.length) * 100 : 0}%"></div>
                      </div>
                    </button>
                  `;
                }).join('')}
              </div>
            </div>
          </div>
        ` : ''}

        <!-- Momentum Wins Tracker -->
        ${(() => {
          const todayDate = stateManager.getTodayDate();
          const todayWins = state.MomentumWins.filter(w => w.date === todayDate);
          const recentWins = state.MomentumWins
            .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
            .slice(0, 5);

          return `
            <div class="rounded-xl border dark:border-gray-700 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-gray-800 dark:to-gray-800 shadow-sm">
              <div class="p-6 border-b border-green-200 dark:border-gray-700">
                <div class="flex items-center justify-between">
                  <div>
                    <h2 class="text-xl font-bold dark:text-white">Momentum Wins</h2>
                    <p class="text-sm text-green-700 dark:text-gray-400 mt-1">Build momentum with small victories</p>
                  </div>
                  <button onclick="addMomentumWin()" class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                    <i class="fas fa-trophy mr-2"></i>Log Win
                  </button>
                </div>
              </div>
              <div class="p-6">
                <div class="flex items-center gap-4 mb-4">
                  <div class="text-center">
                    <div class="text-3xl font-bold text-green-600 dark:text-green-400">${todayWins.length}</div>
                    <p class="text-xs text-green-700 dark:text-gray-400">Today's Wins</p>
                  </div>
                  <div class="text-center">
                    <div class="text-3xl font-bold text-emerald-600 dark:text-emerald-400">${state.MomentumWins.length}</div>
                    <p class="text-xs text-emerald-700 dark:text-gray-400">Total Wins</p>
                  </div>
                </div>

                ${recentWins.length === 0 ? `
                  <div class="text-center py-4">
                    <i class="fas fa-trophy text-3xl text-green-300 dark:text-gray-600 mb-2"></i>
                    <p class="text-green-700 dark:text-gray-400 text-sm">Log your first win to build momentum!</p>
                  </div>
                ` : `
                  <div class="space-y-2">
                    ${recentWins.map(win => `
                      <div class="flex items-center gap-3 p-3 bg-white dark:bg-gray-700 rounded-lg group">
                        <i class="fas fa-check-circle text-green-500"></i>
                        <div class="flex-1">
                          <p class="text-sm font-medium dark:text-gray-300">${UI.sanitize(win.text)}</p>
                          <p class="text-xs text-slate-500 dark:text-gray-400">
                            ${new Date(win.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                            at ${new Date(win.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
                          </p>
                        </div>
                        <button onclick="deleteMomentumWin('${win.id}')"
                                class="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded text-red-500 opacity-0 group-hover:opacity-100 transition-opacity">
                          <i class="fas fa-times text-xs"></i>
                        </button>
                      </div>
                    `).join('')}
                  </div>
                `}
              </div>
            </div>
          `;
        })()}

        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
          <div class="p-6 border-b dark:border-gray-700">
            <div class="flex items-center justify-between">
              <h2 class="text-xl font-bold dark:text-white">Recent A–Z Tasks</h2>
              <button onclick="navigate('AtoZ')" class="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300">
                View All →
              </button>
            </div>
          </div>
          <div class="p-6">
            ${state.AZTask.length === 0 ? `
              <div class="text-center py-8">
                <i class="fas fa-tasks text-4xl text-slate-300 dark:text-gray-600 mb-3"></i>
                <p class="text-slate-500 dark:text-gray-400">No tasks yet. Create your first A–Z task!</p>
                <button onclick="openCreateModal()" class="mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                  Create Task
                </button>
              </div>
            ` : `
              <div class="space-y-3">
                ${state.AZTask.slice(0, 5).map(task => `
                  <div class="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 dark:hover:bg-gray-700">
                    <div class="w-8 h-8 rounded-full flex items-center justify-center font-bold
                      ${task.status === 'Completed' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
                        task.status === 'In Progress' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' :
                        'bg-slate-100 text-slate-700 dark:bg-gray-700 dark:text-gray-300'}">
                      ${task.letter}
                    </div>
                    <div class="flex-1">
                      <p class="font-medium dark:text-gray-300">${UI.sanitize(task.task)}</p>
                      <p class="text-xs text-slate-500 dark:text-gray-400">${UI.sanitize(task.status)}</p>
                    </div>
                    <button onclick="completeTask('${task.id}')" class="p-2 hover:bg-slate-200 dark:hover:bg-gray-600 rounded-lg">
                      <i class="fas fa-check ${task.status === 'Completed' ? 'text-green-600 dark:text-green-400' : 'text-slate-400 dark:text-gray-500'}"></i>
                    </button>
                  </div>
                `).join('')}
              </div>
            `}
          </div>
        </div>
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
        ${(() => {
          const isClosure = false;
          const loops = [];
          if (!isClosure || loops.length === 0) return '';
          return `
          <div class="rounded-xl border-l-4 border-red-500 bg-red-50 dark:bg-red-900/20 p-5 shadow-sm">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-2">
                <i class="fas fa-lock text-red-500"></i>
                <h2 class="text-lg font-bold text-red-800 dark:text-red-300">Closure Queue</h2>
              </div>
              <button onclick="" class="text-xs text-red-600 dark:text-red-400 hover:underline">Manage all loops →</button>
            </div>
            <p class="text-sm text-red-700 dark:text-red-400 mb-3">Close or archive these before creating new work:</p>
            <div class="space-y-2">
              ${loops.map(loop => `
                <div class="flex items-center justify-between p-3 rounded-lg bg-white dark:bg-gray-800">
                  <span class="text-sm font-medium dark:text-gray-200 truncate flex-1">${UI.sanitize(loop.title || 'Untitled loop')}</span>
                  <span class="text-xs text-slate-400 dark:text-gray-500 ml-2">score: ${loop.score || '--'}</span>
                </div>
              `).join('')}
            </div>
          </div>`;
        })()}

        ${(() => {
          const hour = new Date().getHours();
          const blocks = [
            { id: 'morning',   label: 'Morning Scan',    time: '5-7am',   icon: 'fa-sun',          start: 5,  end: 7,  desc: 'Dashboard review, red-alert check, priorities confirmed' },
            { id: 'deepwork',  label: 'Deep Work',       time: '7-12pm',  icon: 'fa-brain',        start: 7,  end: 12, desc: 'High-leverage project execution (protected block)' },
            { id: 'midday',    label: 'Midday Check-in', time: '12-1pm',  icon: 'fa-battery-half', start: 12, end: 13, desc: 'Energy check, nutrition, micro-rest' },
            { id: 'afternoon', label: 'Afternoon',       time: '1-5pm',   icon: 'fa-tools',        start: 13, end: 17, desc: 'Continuation or household navigation' },
            { id: 'evening',   label: 'Evening Ops',     time: '5-7pm',   icon: 'fa-home',         start: 17, end: 19, desc: 'Finance tracking, mobility checks, household tasks' },
            { id: 'night',     label: 'Night Audit',     time: '7-9pm',   icon: 'fa-clipboard-check', start: 19, end: 21, desc: 'Daily audit, journal, prep tomorrow' },
            { id: 'close',     label: 'Close',           time: '9-10pm',  icon: 'fa-moon',         start: 21, end: 22, desc: 'Energy recovery, plan next day' },
          ];
          return `
          <details class="rounded-xl border dark:border-gray-700 bg-gray-900 shadow-sm" open>
            <summary class="p-4 cursor-pointer flex items-center justify-between list-none">
              <div class="flex items-center gap-2">
                <i class="fas fa-clock text-blue-400"></i>
                <span class="text-sm font-bold text-gray-200">Daily Operating Protocol</span>
              </div>
              <i class="fas fa-chevron-down text-gray-500 text-xs transition-transform"></i>
            </summary>
            <div class="px-4 pb-4">
              <div class="grid grid-cols-7 gap-1">
                ${blocks.map(b => {
                  const active = hour >= b.start && hour < b.end;
                  const past = hour >= b.end;
                  return `
                    <div class="text-center p-2 rounded-lg ${active ? 'bg-blue-600/30 ring-1 ring-blue-500' : past ? 'bg-gray-800 opacity-50' : 'bg-gray-800'} transition">
                      <i class="fas ${b.icon} ${active ? 'text-blue-400' : past ? 'text-gray-600' : 'text-gray-400'} text-sm"></i>
                      <p class="text-[10px] font-bold ${active ? 'text-blue-300' : 'text-gray-400'} mt-1">${b.label}</p>
                      <p class="text-[9px] ${active ? 'text-blue-400' : 'text-gray-600'}">${b.time}</p>
                    </div>
                  `;
                }).join('')}
              </div>
              <p class="text-[10px] text-gray-500 mt-2 text-center">
                ${blocks.find(b => hour >= b.start && hour < b.end)?.desc || 'Outside protocol hours'}
              </p>
            </div>
          </details>
          `;
        })()}

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

        ${(() => {
          const ideas = [];
          if (ideas.length === 0) return '';
          // Filter out ideas that already match an existing A-Z task title
          const existingTitles = new Set(state.AZTask.map(t => t.task.toLowerCase()));
          const newIdeas = ideas.filter(i => !existingTitles.has((i.canonical_title || '').toLowerCase()));
          if (newIdeas.length === 0) return '';
          return `
          <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
            <div class="p-6 border-b dark:border-gray-700">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <i class="fas fa-lightbulb text-amber-500"></i>
                  <h2 class="text-lg font-bold dark:text-white">From Idea Registry</h2>
                </div>
                <button onclick="" class="text-xs text-blue-600 dark:text-blue-400 hover:underline">Browse all →</button>
              </div>
              <p class="text-sm text-slate-500 dark:text-gray-400 mt-1">High-priority ideas not yet in your A-Z list</p>
            </div>
            <div class="p-6 space-y-3">
              ${newIdeas.slice(0, 5).map(idea => `
                <div class="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-gray-700/50">
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium dark:text-gray-200 truncate">${UI.sanitize(idea.canonical_title || 'Untitled')}</p>
                    <span class="text-xs text-slate-500 dark:text-gray-400">${idea.category || ''} • priority: ${(idea.priority_score || 0).toFixed(2)}</span>
                  </div>
                  <button onclick="addIdeaToAZ('${UI.sanitize(idea.canonical_title || 'Untitled')}')" class="ml-3 px-3 py-1 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 whitespace-nowrap">
                    Add to A-Z
                  </button>
                </div>
              `).join('')}
            </div>
          </div>`;
        })()}
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
          ${[...state.FocusArea].sort((a, b) => (b.leverageWeight || 0) - (a.leverageWeight || 0)).map(area => {
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

  Calendar() {
    const view = state.calendarView || 'month';
    const selectedDate = state.calendarDate || stateManager.getTodayDate();
    const today = stateManager.getTodayDate();

    // Parse selected date for navigation
    const [selYear, selMonth, selDay] = selectedDate.split('-').map(Number);
    const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    const dayNames = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

    function renderViewToggle() {
      const views = [
        { id: 'month', icon: 'fa-calendar', label: 'Month' },
        { id: 'week', icon: 'fa-calendar-week', label: 'Week' },
        { id: 'day', icon: 'fa-calendar-day', label: 'Day' }
      ];
      return views.map(v => `
        <button onclick="calendarSetView('${v.id}')"
          class="px-4 py-2 text-sm font-medium rounded-lg transition-colors ${view === v.id
            ? 'bg-blue-600 text-white'
            : 'bg-gray-700/50 text-gray-300 hover:bg-gray-600'}">
          <i class="fas ${v.icon} mr-1"></i>${v.label}
        </button>
      `).join('');
    }

    function getDayData(dateStr) {
      const plan = state.DayPlans[dateStr];
      if (!plan) return null;
      const progress = Helpers.calculateDailyProgress(dateStr);
      return { plan, progress };
    }

    function renderDayCell(dateStr, dayNum, isCurrentMonth) {
      const isToday = dateStr === today;
      const isSelected = dateStr === selectedDate;
      const data = getDayData(dateStr);
      const dayType = data?.plan?.day_type;
      const progress = data?.progress?.overall || 0;
      const hasData = !!data;

      const typeColors = { A: 'text-blue-400', B: 'text-amber-400', C: 'text-red-400' };
      const progressDot = hasData
        ? (progress >= 70 ? 'bg-green-500' : progress >= 50 ? 'bg-yellow-500' : 'bg-gray-500')
        : '';

      const clickAction = hasData ? `calendarSelectDate('${dateStr}')` : `showCreatePlanModal('${dateStr}')`;

      return `
        <button onclick="${clickAction}"
          class="relative p-2 h-20 rounded-lg border transition-all text-left
            ${isCurrentMonth ? 'dark:border-gray-700' : 'dark:border-gray-800 opacity-40'}
            ${isToday ? 'ring-2 ring-blue-500' : ''}
            ${isSelected ? 'dark:bg-blue-900/30 dark:border-blue-700' : 'dark:bg-gray-800/50 hover:dark:bg-gray-700/50'}">
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium ${isToday ? 'text-blue-400' : 'dark:text-gray-300'}">${dayNum}</span>
            ${dayType ? `<span class="text-xs font-bold ${typeColors[dayType] || 'text-gray-400'}">${dayType}</span>` : ''}
          </div>
          ${hasData ? `
            <div class="mt-1 flex items-center gap-1">
              <span class="w-2 h-2 rounded-full ${progressDot}"></span>
              <span class="text-xs text-gray-400">${progress}%</span>
            </div>
            ${data.plan.time_blocks?.length ? `<div class="text-xs text-gray-500 mt-0.5">${data.plan.time_blocks.filter(b=>b.completed).length}/${data.plan.time_blocks.length} blocks</div>` : ''}
          ` : `
            ${isCurrentMonth ? '<div class="mt-2 text-center"><i class="fas fa-plus text-gray-600 text-xs"></i></div>' : ''}
          `}
        </button>`;
    }

    function renderMonthView() {
      const firstDay = new Date(selYear, selMonth - 1, 1);
      const lastDay = new Date(selYear, selMonth, 0);
      const startDow = firstDay.getDay();
      const daysInMonth = lastDay.getDate();

      // Previous month padding
      const prevMonth = new Date(selYear, selMonth - 1, 0);
      const prevDays = prevMonth.getDate();

      let cells = '';

      // Leading days from previous month
      for (let i = startDow - 1; i >= 0; i--) {
        const d = prevDays - i;
        const pm = selMonth - 1 < 1 ? 12 : selMonth - 1;
        const py = selMonth - 1 < 1 ? selYear - 1 : selYear;
        const dateStr = `${py}-${String(pm).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        cells += renderDayCell(dateStr, d, false);
      }

      // Current month days
      for (let d = 1; d <= daysInMonth; d++) {
        const dateStr = `${selYear}-${String(selMonth).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        cells += renderDayCell(dateStr, d, true);
      }

      // Trailing days
      const totalCells = startDow + daysInMonth;
      const remaining = (7 - (totalCells % 7)) % 7;
      for (let d = 1; d <= remaining; d++) {
        const nm = selMonth + 1 > 12 ? 1 : selMonth + 1;
        const ny = selMonth + 1 > 12 ? selYear + 1 : selYear;
        const dateStr = `${ny}-${String(nm).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        cells += renderDayCell(dateStr, d, false);
      }

      return `
        <div class="grid grid-cols-7 gap-1 mb-2">
          ${dayNames.map(d => `<div class="text-center text-xs font-medium text-gray-500 py-2">${d}</div>`).join('')}
        </div>
        <div class="grid grid-cols-7 gap-1">${cells}</div>
      `;
    }

    function renderWeekView() {
      const sel = new Date(selYear, selMonth - 1, selDay);
      const weekStart = new Date(sel);
      weekStart.setDate(sel.getDate() - sel.getDay());

      let cols = '';
      for (let i = 0; i < 7; i++) {
        const d = new Date(weekStart);
        d.setDate(weekStart.getDate() + i);
        const dateStr = d.toISOString().slice(0, 10);
        const isToday = dateStr === today;
        const data = getDayData(dateStr);
        const dayType = data?.plan?.day_type;
        const progress = data?.progress?.overall || 0;
        const timeBlocks = data?.plan?.time_blocks || [];
        const typeColors = { A: 'bg-blue-900/30 border-blue-700', B: 'bg-amber-900/30 border-amber-700', C: 'bg-red-900/30 border-red-700' };

        cols += `
          <div class="rounded-xl border dark:border-gray-700 ${isToday ? 'ring-2 ring-blue-500' : ''} ${dayType ? typeColors[dayType] || 'dark:bg-gray-800' : 'dark:bg-gray-800'} p-3 min-h-[300px] flex flex-col cursor-pointer" onclick="calendarSelectDate('${dateStr}')">
            <div class="text-center mb-3 pb-2 border-b dark:border-gray-600">
              <div class="text-xs text-gray-400">${dayNames[d.getDay()]}</div>
              <div class="text-lg font-bold ${isToday ? 'text-blue-400' : 'dark:text-white'}">${d.getDate()}</div>
              ${dayType ? `<span class="text-xs font-bold px-2 py-0.5 rounded-full ${dayType === 'A' ? 'bg-blue-500/20 text-blue-300' : dayType === 'B' ? 'bg-amber-500/20 text-amber-300' : 'bg-red-500/20 text-red-300'}">${dayType}-Day</span>` : ''}
            </div>
            ${data ? `
              <div class="mb-2">
                <div class="flex items-center justify-between text-xs mb-1">
                  <span class="text-gray-400">Progress</span>
                  <span class="font-medium ${progress >= 70 ? 'text-green-400' : progress >= 50 ? 'text-yellow-400' : 'text-gray-400'}">${progress}%</span>
                </div>
                <div class="w-full bg-gray-700 rounded-full h-1.5">
                  <div class="${progress >= 70 ? 'bg-green-500' : progress >= 50 ? 'bg-yellow-500' : 'bg-gray-500'} h-1.5 rounded-full" style="width:${progress}%"></div>
                </div>
              </div>
              <div class="flex-1 space-y-1 overflow-y-auto">
                ${timeBlocks.slice(0, 6).map(b => `
                  <div class="flex items-center gap-1.5 text-xs">
                    <span class="w-3 h-3 rounded-full flex-shrink-0 flex items-center justify-center ${b.completed ? 'bg-green-500/20 text-green-400' : 'bg-gray-700 text-gray-500'}">
                      ${b.completed ? '<i class="fas fa-check" style="font-size:6px"></i>' : ''}
                    </span>
                    <span class="truncate ${b.completed ? 'text-gray-500 line-through' : 'text-gray-300'}">${UI.sanitize(b.title)}</span>
                  </div>
                `).join('')}
                ${timeBlocks.length > 6 ? `<div class="text-xs text-gray-500">+${timeBlocks.length - 6} more</div>` : ''}
              </div>
              ${data.plan.baseline_goal?.text ? `
                <div class="mt-2 pt-2 border-t dark:border-gray-600">
                  <div class="flex items-center gap-1 text-xs">
                    <i class="fas ${data.plan.baseline_goal.completed ? 'fa-check-circle text-green-400' : 'fa-circle text-gray-500'}" style="font-size:8px"></i>
                    <span class="truncate text-gray-400">${UI.sanitize(data.plan.baseline_goal.text)}</span>
                  </div>
                </div>
              ` : ''}
            ` : `
              <div class="flex-1 flex items-center justify-center">
                <button onclick="event.stopPropagation();showCreatePlanModal('${dateStr}')" class="px-3 py-2 rounded-lg border border-dashed dark:border-gray-600 text-xs text-gray-400 hover:text-gray-300 hover:border-gray-500 transition-colors">
                  <i class="fas fa-plus mr-1"></i>Create Plan
                </button>
              </div>
            `}
          </div>
        `;
      }

      return `<div class="grid grid-cols-7 gap-2">${cols}</div>`;
    }

    function renderDayView() {
      const dateStr = selectedDate;
      const data = getDayData(dateStr);
      const d = new Date(selYear, selMonth - 1, selDay);
      const dayLabel = d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
      const isToday = dateStr === today;

      if (!data) {
        return `
          <div class="rounded-xl border dark:border-gray-700 dark:bg-gray-800 p-8 text-center">
            <i class="fas fa-calendar-plus text-4xl text-gray-500 mb-4"></i>
            <h3 class="text-lg font-bold dark:text-white mb-2">${dayLabel}</h3>
            <p class="text-gray-400 mb-4">No plan for this day yet.</p>
            <button onclick="showCreatePlanModal('${dateStr}')" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"><i class="fas fa-plus mr-2"></i>Create Plan</button>
          </div>
        `;
      }

      const { plan, progress } = data;
      const dayType = plan.day_type;
      const typeLabel = { A: 'Optimal Day', B: 'Low Energy Day', C: 'Chaos Day' };
      const typeColor = { A: 'blue', B: 'amber', C: 'red' };
      const color = typeColor[dayType] || 'gray';

      // Momentum wins for this day
      const dayWins = (state.MomentumWins || []).filter(w => w.date === dateStr);

      // Routines
      const routineTypes = Object.keys(state.Routine);
      const routinesHtml = routineTypes.map(name => {
        const completionData = plan.routines_completed?.[name] || { completed: false, steps: {} };
        const steps = state.Routine[name] || [];
        const completedSteps = Object.values(completionData.steps || {}).filter(Boolean).length;
        return `
          <div class="flex items-center justify-between p-2 rounded-lg dark:bg-gray-700/50">
            <div class="flex items-center gap-2">
              <i class="fas ${completionData.completed ? 'fa-check-circle text-green-400' : 'fa-circle text-gray-500'} text-sm"></i>
              <span class="text-sm dark:text-gray-300">${UI.sanitize(name)}</span>
            </div>
            <span class="text-xs text-gray-400">${completedSteps}/${steps.length}</span>
          </div>
        `;
      }).join('');

      return `
        <div class="space-y-4">
          <!-- Day Header -->
          <div class="rounded-xl border dark:border-gray-700 dark:bg-gray-800 p-6">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="text-xl font-bold dark:text-white">${dayLabel}</h3>
                ${dayType ? `<button onclick="setDayTypeForDate('${dateStr}','${dayType === 'A' ? 'B' : dayType === 'B' ? 'C' : 'A'}')" class="inline-block mt-1 text-xs font-bold px-3 py-1 rounded-full bg-${color}-500/20 text-${color}-300 hover:opacity-80 cursor-pointer" title="Click to change day type">${dayType}-Day: ${typeLabel[dayType] || ''} <i class="fas fa-exchange-alt ml-1 text-xs"></i></button>` : ''}
              </div>
              <div class="text-right">
                <div class="text-3xl font-bold ${progress.overall >= 70 ? 'text-green-400' : progress.overall >= 50 ? 'text-yellow-400' : 'text-gray-400'}">${progress.overall}%</div>
                <div class="text-xs text-gray-400">Overall Progress</div>
              </div>
            </div>
            <div class="w-full bg-gray-700 rounded-full h-2">
              <div class="${progress.overall >= 70 ? 'bg-green-500' : progress.overall >= 50 ? 'bg-yellow-500' : 'bg-gray-500'} h-2 rounded-full transition-all" style="width:${progress.overall}%"></div>
            </div>
            ${isToday ? '<div class="mt-3"><button onclick="navigate(\'Daily\')" class="text-sm text-blue-400 hover:text-blue-300"><i class="fas fa-edit mr-1"></i>Edit in Daily View</button></div>' : ''}
          </div>

          <div class="grid md:grid-cols-2 gap-4">
            <!-- Time Blocks -->
            <div class="rounded-xl border dark:border-gray-700 dark:bg-gray-800 p-6">
              <h4 class="text-lg font-bold dark:text-white mb-3"><i class="fas fa-clock text-blue-400 mr-2"></i>Time Blocks</h4>
              <div class="space-y-2">
                ${(plan.time_blocks || []).map(b => `
                  <button onclick="toggleTimeBlockCompletionForDate('${dateStr}','${b.id}')" class="flex items-center gap-3 p-2 rounded-lg w-full text-left cursor-pointer hover:bg-gray-700/50 transition-colors ${b.completed ? 'dark:bg-green-900/10' : 'dark:bg-gray-700/30'}">
                    <i class="fas ${b.completed ? 'fa-check-circle text-green-400' : 'fa-circle text-gray-500'} text-sm"></i>
                    <span class="text-xs text-gray-400 w-14">${UI.sanitize(b.time || '')}</span>
                    <span class="text-sm ${b.completed ? 'text-gray-500 line-through' : 'dark:text-gray-300'}">${UI.sanitize(b.title)}</span>
                  </button>
                `).join('')}
                ${!plan.time_blocks?.length ? '<p class="text-sm text-gray-500">No time blocks</p>' : ''}
                <button onclick="showNewEventModal('${dateStr}')" class="flex items-center justify-center gap-2 p-2 rounded-lg w-full border border-dashed dark:border-gray-600 text-gray-400 hover:text-gray-300 hover:border-gray-500 transition-colors mt-2">
                  <i class="fas fa-plus text-xs"></i><span class="text-xs">New Event</span>
                </button>
              </div>
            </div>

            <!-- Goals & Routines -->
            <div class="space-y-4">
              <div class="rounded-xl border dark:border-gray-700 dark:bg-gray-800 p-6">
                <h4 class="text-lg font-bold dark:text-white mb-3"><i class="fas fa-bullseye text-green-400 mr-2"></i>Goals</h4>
                ${plan.baseline_goal?.text ? `
                  <button onclick="toggleGoalCompletionForDate('${dateStr}','baseline')" class="flex items-center gap-2 p-2 rounded-lg dark:bg-gray-700/30 mb-2 w-full text-left cursor-pointer hover:bg-gray-700/50 transition-colors">
                    <i class="fas ${plan.baseline_goal.completed ? 'fa-check-circle text-green-400' : 'fa-circle text-gray-500'} text-sm"></i>
                    <div>
                      <div class="text-xs text-gray-400">Baseline</div>
                      <div class="text-sm ${plan.baseline_goal.completed ? 'text-gray-500 line-through' : 'dark:text-gray-300'}">${UI.sanitize(plan.baseline_goal.text)}</div>
                    </div>
                  </button>
                ` : ''}
                ${plan.stretch_goal?.text ? `
                  <button onclick="toggleGoalCompletionForDate('${dateStr}','stretch')" class="flex items-center gap-2 p-2 rounded-lg dark:bg-gray-700/30 w-full text-left cursor-pointer hover:bg-gray-700/50 transition-colors">
                    <i class="fas ${plan.stretch_goal.completed ? 'fa-check-circle text-green-400' : 'fa-circle text-gray-500'} text-sm"></i>
                    <div>
                      <div class="text-xs text-gray-400">Stretch</div>
                      <div class="text-sm ${plan.stretch_goal.completed ? 'text-gray-500 line-through' : 'dark:text-gray-300'}">${UI.sanitize(plan.stretch_goal.text)}</div>
                    </div>
                  </button>
                ` : ''}
                ${!plan.baseline_goal?.text && !plan.stretch_goal?.text ? '<p class="text-sm text-gray-500">No goals set</p>' : ''}
              </div>

              <div class="rounded-xl border dark:border-gray-700 dark:bg-gray-800 p-6">
                <h4 class="text-lg font-bold dark:text-white mb-3"><i class="fas fa-clipboard-check text-purple-400 mr-2"></i>Routines</h4>
                <div class="space-y-2">${routinesHtml || '<p class="text-sm text-gray-500">No routines</p>'}</div>
              </div>
            </div>
          </div>

          ${dayWins.length > 0 ? `
            <div class="rounded-xl border dark:border-gray-700 dark:bg-gray-800 p-6">
              <h4 class="text-lg font-bold dark:text-white mb-3"><i class="fas fa-trophy text-yellow-400 mr-2"></i>Momentum Wins</h4>
              <div class="space-y-2">
                ${dayWins.map(w => `
                  <div class="flex items-center gap-2 p-2 rounded-lg dark:bg-yellow-900/10">
                    <i class="fas fa-star text-yellow-400 text-xs"></i>
                    <span class="text-sm dark:text-gray-300">${UI.sanitize(w.text || w.description || '')}</span>
                  </div>
                `).join('')}
              </div>
            </div>
          ` : ''}

          ${plan.notes ? `
            <div class="rounded-xl border dark:border-gray-700 dark:bg-gray-800 p-6">
              <h4 class="text-lg font-bold dark:text-white mb-3"><i class="fas fa-sticky-note text-gray-400 mr-2"></i>Notes</h4>
              <p class="text-sm dark:text-gray-300 whitespace-pre-wrap">${UI.sanitize(plan.notes)}</p>
            </div>
          ` : ''}
        </div>
      `;
    }

    // Navigation label
    let navLabel = '';
    if (view === 'month') {
      navLabel = `${monthNames[selMonth - 1]} ${selYear}`;
    } else if (view === 'week') {
      const sel = new Date(selYear, selMonth - 1, selDay);
      const weekStart = new Date(sel);
      weekStart.setDate(sel.getDate() - sel.getDay());
      const weekEnd = new Date(weekStart);
      weekEnd.setDate(weekStart.getDate() + 6);
      navLabel = `${weekStart.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – ${weekEnd.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`;
    } else {
      const d = new Date(selYear, selMonth - 1, selDay);
      navLabel = d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
    }

    // Month summary stats
    let monthStats = '';
    if (view === 'month') {
      const daysInMonth = new Date(selYear, selMonth, 0).getDate();
      let planned = 0, highDays = 0, totalProgress = 0, progressDays = 0;
      for (let d = 1; d <= daysInMonth; d++) {
        const ds = `${selYear}-${String(selMonth).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        if (state.DayPlans[ds]) {
          planned++;
          const p = Helpers.calculateDailyProgress(ds).overall;
          totalProgress += p;
          progressDays++;
          if (p >= 70) highDays++;
        }
      }
      const avg = progressDays ? Math.round(totalProgress / progressDays) : 0;
      monthStats = `
        <div class="grid grid-cols-3 gap-3 mb-4">
          <div class="rounded-lg dark:bg-gray-700/50 p-3 text-center">
            <div class="text-xl font-bold dark:text-white">${planned}</div>
            <div class="text-xs text-gray-400">Days Planned</div>
          </div>
          <div class="rounded-lg dark:bg-gray-700/50 p-3 text-center">
            <div class="text-xl font-bold ${avg >= 70 ? 'text-green-400' : avg >= 50 ? 'text-yellow-400' : 'dark:text-white'}">${avg}%</div>
            <div class="text-xs text-gray-400">Avg Progress</div>
          </div>
          <div class="rounded-lg dark:bg-gray-700/50 p-3 text-center">
            <div class="text-xl font-bold text-green-400">${highDays}</div>
            <div class="text-xs text-gray-400">70%+ Days</div>
          </div>
        </div>
      `;
    }

    return `
      <div class="space-y-4 fade-in">
        <div class="rounded-xl border dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
          <!-- Header -->
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              ${renderViewToggle()}
            </div>
            <button onclick="calendarGoToday()" class="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-700/50 text-gray-300 hover:bg-gray-600">Today</button>
          </div>

          <!-- Navigation -->
          <div class="flex items-center justify-between mb-4">
            <button onclick="calendarPrev()" class="p-2 rounded-lg hover:bg-gray-700 text-gray-400 hover:text-white transition-colors">
              <i class="fas fa-chevron-left"></i>
            </button>
            <h2 class="text-xl font-bold dark:text-white">${navLabel}</h2>
            <button onclick="calendarNext()" class="p-2 rounded-lg hover:bg-gray-700 text-gray-400 hover:text-white transition-colors">
              <i class="fas fa-chevron-right"></i>
            </button>
          </div>

          ${monthStats}

          <!-- View Content -->
          ${view === 'month' ? renderMonthView() : view === 'week' ? renderWeekView() : renderDayView()}
        </div>
      </div>
    `;
  },

  // === LIFE DOMAIN SCREENS ===










};

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { screens, renderNav, navigate, ScreenRenderers };
}
