// CycleBoard Strategic Leverage Router
// Bridges Atlas leverage intelligence into daily execution directives

const StrategicRouter = {
  priorities: null,
  initialized: false,
  error: null,
  stale: false,
  staleHours: 0,

  async init() {
    if (this.initialized) return;
    await this._loadData(true);
  },

  async _loadData(isFirstLoad) {
    try {
      const response = await fetch('brain/strategic_priorities.json');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const text = await response.text();
      if (!text.trim()) {
        throw new Error('Empty response');
      }

      const newPriorities = JSON.parse(text);

      if (!newPriorities || typeof newPriorities !== 'object') {
        throw new Error('Invalid priorities structure');
      }

      // On refresh: skip if data unchanged
      if (!isFirstLoad && newPriorities.generated && this.priorities?.generated
          && newPriorities.generated === this.priorities.generated) {
        return;
      }

      this.priorities = newPriorities;
      this.initialized = true;
      this.error = null;
      this.checkStaleness();

      // Remove old banner before re-injecting
      const existing = document.getElementById('strategic-directive');
      if (existing) existing.remove();

      this.injectDirectiveBanner();
      this.reweightFocusAreas();

      if (typeof navigate === 'function' && typeof state !== 'undefined') {
        navigate(state.screen || 'Home');
      }

    } catch (error) {
      this.error = error.message;
      this.initialized = true;

      if (error.message.includes('404')) {
        if (isFirstLoad) console.log('Strategic router offline. Run: python build_strategic_priorities.py');
      } else {
        console.warn('Strategic router error:', error.message);
      }
    }
  },

  async refresh() {
    await this._loadData(false);
  },

  checkStaleness() {
    if (!this.priorities) return;
    const result = DataFreshness.check(this.priorities.generated);
    this.stale = result.stale;
    this.staleHours = result.ageHours;
    this.freshness = result;
  },

  // === DATA ACCESSORS ===

  getTopCluster() {
    if (!this.priorities) return null;
    const clusters = this.priorities.top_clusters || [];
    return clusters[0] || null;
  },

  getDailyDirective() {
    if (!this.priorities) return null;
    return this.priorities.daily_directive || null;
  },

  getFocusAreaWeights() {
    if (!this.priorities) return null;
    return this.priorities.focus_area_weights || null;
  },

  getClusterForFocusArea(areaName) {
    const weights = this.getFocusAreaWeights();
    if (!weights || !weights[areaName]) return null;
    return weights[areaName];
  },

  shouldEscalateMode() {
    const directive = this.getDailyDirective();
    return directive?.mode_escalation || null;
  },

  // === DOM: STRATEGIC DIRECTIVE BANNER ===

  injectDirectiveBanner() {
    if (!this.priorities) return;

    const top = this.getTopCluster();
    const directive = this.getDailyDirective();
    if (!top || !directive) return;

    // Don't inject if already exists
    if (document.getElementById('strategic-directive')) return;

    const cognitiveBanner = document.getElementById('cognitive-directive');
    const banner = document.createElement('div');
    banner.id = 'strategic-directive';

    const gapColors = {
      'high_leverage_low_execution': 'from-indigo-600 to-violet-600',
      'high_leverage_high_execution': 'from-emerald-600 to-teal-600',
      'balanced': 'from-slate-600 to-gray-600',
      'low_leverage_low_execution': 'from-gray-500 to-slate-500',
    };

    const gapLabels = {
      'high_leverage_low_execution': 'BUILD PRIORITY',
      'high_leverage_high_execution': 'SCALE READY',
      'balanced': 'BALANCED',
      'low_leverage_low_execution': 'LOW PRIORITY',
    };

    const gradientClass = gapColors[top.gap] || gapColors['balanced'];
    const gapLabel = gapLabels[top.gap] || 'BALANCED';

    banner.className = `w-full text-white shadow-lg bg-gradient-to-r ${gradientClass}`;
    banner.style.position = 'sticky';
    banner.style.top = cognitiveBanner ? 'auto' : '0';
    banner.style.zIndex = '49';

    const bannerStaleBadge = this.stale
      ? `<span class="ml-2 text-xs font-medium px-2 py-0.5 rounded-full bg-yellow-400/20 text-yellow-200">
          <i class="fas fa-clock mr-1"></i>${this.staleHours < 0 ? 'Age unknown' : `${this.staleHours}h old`}
        </span>`
      : '';

    banner.innerHTML = `
      <div class="max-w-7xl mx-auto px-4 py-3">
        <div class="flex items-center justify-between">
          <div class="flex-1">
            <div class="text-xs uppercase tracking-wider opacity-75 mb-1">
              <i class="fas fa-route mr-1"></i> Strategic Leverage Router${bannerStaleBadge}
            </div>
            <div class="flex items-center gap-6 flex-wrap">
              <div>
                <div class="text-xs opacity-75">FOCUS</div>
                <div class="text-lg font-bold">${directive.primary_focus}</div>
              </div>
              <div class="cursor-pointer hover:opacity-80 transition" onclick="AtlasNav.open('atlas')" title="View cluster in Cognitive Atlas">
                <div class="text-xs opacity-75">CLUSTER</div>
                <div class="text-lg font-bold underline decoration-dotted">C${top.cluster_id}</div>
              </div>
              <div>
                <div class="text-xs opacity-75">DEEP BLOCK</div>
                <div class="text-lg font-bold">${directive.suggested_deep_block_mins}m</div>
              </div>
              <div>
                <div class="text-xs opacity-75">GAP</div>
                <div class="text-sm font-bold">${gapLabel}</div>
              </div>
              <div class="flex-1">
                <div class="text-xs opacity-75">DIRECTIVE</div>
                <div class="text-sm font-medium">${directive.primary_action}</div>
              </div>
            </div>
          </div>
          <button onclick="StrategicRouter.toggleBanner()" class="p-2 hover:bg-white/20 rounded-lg transition" title="Minimize">
            <i class="fas fa-chevron-up"></i>
          </button>
        </div>
      </div>
    `;

    // Insert after cognitive banner or at top of body
    if (cognitiveBanner) {
      cognitiveBanner.parentNode.insertBefore(banner, cognitiveBanner.nextSibling);
    } else {
      document.body.insertBefore(banner, document.body.firstChild);
    }

    // If there's a mode escalation, log it
    const escalation = this.shouldEscalateMode();
    if (escalation) {
      console.log('[SLR] Mode escalation:', escalation);
    }
  },

  toggleBanner() {
    const banner = document.getElementById('strategic-directive');
    if (!banner) return;

    if (banner.style.display === 'none') {
      banner.style.display = 'block';
    } else {
      banner.style.display = 'none';
    }
  },

  // === FOCUS AREA REWEIGHTING ===

  reweightFocusAreas() {
    const weights = this.getFocusAreaWeights();
    if (!weights || !state.FocusArea) return [];

    // Sort by strategic leverage weight and annotate each area
    const sorted = [...state.FocusArea].sort((a, b) => {
      const wA = weights[a.name]?.weight || 0;
      const wB = weights[b.name]?.weight || 0;
      return wB - wA;
    }).map(area => ({
      ...area,
      leverageWeight: weights[area.name]?.weight || 0
    }));

    // Persist reordered areas to state
    state.FocusArea = sorted;
    stateManager.update({ FocusArea: sorted });
    console.log('[SLR] Focus areas reweighted:', sorted.map(a => `${a.name}(${a.leverageWeight})`).join(', '));

    return sorted;
  },

  getWeightForArea(areaName) {
    const weights = this.getFocusAreaWeights();
    if (!weights || !weights[areaName]) return null;
    return weights[areaName].weight;
  },

  // === A-Z TASK SUGGESTION ===

  suggestAZOverride() {
    const top = this.getTopCluster();
    if (!top || !state.AZTask) return null;

    const ngrams = (top.top_ngrams || []).slice(0, 5);
    if (ngrams.length === 0) return null;

    // Search A-Z tasks for ngram matches
    for (const task of state.AZTask) {
      if (task.status === 'Completed') continue;
      const title = (task.task || '').toLowerCase();
      for (const ngram of ngrams) {
        if (title.includes(ngram.toLowerCase())) {
          return {
            task: task,
            ngram: ngram,
            cluster_id: top.cluster_id,
            message: `Elevate: ${task.task} (aligned with C${top.cluster_id})`
          };
        }
      }
    }

    return {
      task: null,
      cluster_id: top.cluster_id,
      message: `No A-task aligned with C${top.cluster_id}. Consider creating one for: ${top.label}`
    };
  },

  // === TIME BLOCK SUGGESTION ===

  suggestTimeBlock() {
    const directive = this.getDailyDirective();
    if (!directive) return null;

    return {
      focus: directive.primary_focus,
      mins: directive.suggested_deep_block_mins,
      cluster_id: directive.primary_cluster,
      stretch: directive.stretch_goal,
    };
  },

  // === RENDER HELPERS (for screens.js injection) ===

  renderStrategicCard() {
    if (!this.priorities) {
      return `
        <div class="rounded-xl border-l-4 border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 p-6 shadow-sm opacity-60">
          <div class="flex items-center gap-2 mb-3">
            <i class="fas fa-route text-gray-400"></i>
            <h2 class="text-lg font-bold dark:text-white">Strategic Directive</h2>
          </div>
          <p class="text-sm text-gray-400">Strategic data offline</p>
        </div>
      `;
    }

    const top = this.getTopCluster();
    const directive = this.getDailyDirective();
    if (!top || !directive) return '';

    const gapColors = {
      'high_leverage_low_execution': 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20',
      'high_leverage_high_execution': 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20',
      'balanced': 'border-slate-400 bg-slate-50 dark:bg-slate-800',
      'low_leverage_low_execution': 'border-gray-400 bg-gray-50 dark:bg-gray-800',
    };

    const cardClass = gapColors[top.gap] || gapColors['balanced'];

    const staleBadge = this.stale
      ? `<span class="ml-2 text-xs font-medium px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300">
          <i class="fas fa-clock mr-1"></i>Stale: ${this.freshness?.ageText || 'age unknown'}
        </span>`
      : '';

    return `
      <div class="rounded-xl border-l-4 ${cardClass} p-6 shadow-sm">
        <div class="flex items-center gap-2 mb-3">
          <i class="fas fa-route text-indigo-500"></i>
          <h2 class="text-lg font-bold dark:text-white">Strategic Directive</h2>
          ${staleBadge}
        </div>
        <p class="text-sm font-medium dark:text-gray-200 mb-4">${directive.primary_action}</p>
        <div class="grid grid-cols-3 gap-4 text-center">
          <div>
            <div class="text-xs text-slate-500 dark:text-gray-400">Focus</div>
            <div class="font-bold dark:text-white">${directive.primary_focus}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-gray-400">Deep Block</div>
            <div class="font-bold dark:text-white">${directive.suggested_deep_block_mins}m</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-gray-400">Leverage</div>
            <div class="font-bold dark:text-white">${top.normalized_leverage.toFixed(1)}</div>
          </div>
        </div>
        ${directive.stretch_goal ? `
          <div class="mt-4 pt-3 border-t dark:border-gray-700">
            <div class="text-xs text-slate-500 dark:text-gray-400 mb-1">Stretch Goal</div>
            <div class="text-sm font-medium dark:text-gray-300">${directive.stretch_goal}</div>
          </div>
        ` : ''}
        <div class="mt-3 text-xs text-gray-400">Updated ${this.freshness?.ageText || DataFreshness.check(this.priorities.generated).ageText}</div>
      </div>
    `;
  },

  renderFocusAreaBadge(areaName) {
    const weight = this.getWeightForArea(areaName);
    if (weight === null) return '';

    const color = weight >= 7 ? 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300' :
                  weight >= 4 ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300' :
                  weight > 0 ? 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300' :
                  'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400';

    return `<span class="ml-2 text-xs font-bold px-2 py-0.5 rounded-full ${color}" title="Strategic leverage weight">${weight}</span>`;
  },

  renderAZSuggestion() {
    const suggestion = this.suggestAZOverride();
    if (!suggestion) return '';

    const color = suggestion.task
      ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20'
      : 'border-amber-500 bg-amber-50 dark:bg-amber-900/20';

    const icon = suggestion.task ? 'fa-arrow-up' : 'fa-lightbulb';

    return `
      <div class="rounded-lg border-l-4 ${color} p-3 mb-4">
        <div class="flex items-center gap-2">
          <i class="fas ${icon} text-sm ${suggestion.task ? 'text-indigo-500' : 'text-amber-500'}"></i>
          <span class="text-sm font-medium dark:text-gray-200">${suggestion.message}</span>
        </div>
      </div>
    `;
  },

  renderTimeBlockSuggestion() {
    const block = this.suggestTimeBlock();
    if (!block) return '';

    return `
      <div class="rounded-lg border border-dashed border-indigo-400 dark:border-indigo-600 bg-indigo-50/50 dark:bg-indigo-900/10 p-3 mb-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <i class="fas fa-clock text-indigo-500"></i>
            <span class="text-sm dark:text-gray-200">
              Suggested: <strong>${block.mins}m</strong> deep block for <strong>${block.focus}</strong>
            </span>
          </div>
          <button onclick="StrategicRouter.addSuggestedBlock()" class="text-xs px-3 py-1 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition">
            Add Block
          </button>
        </div>
      </div>
    `;
  },

  addSuggestedBlock() {
    const block = this.suggestTimeBlock();
    if (!block || !state.DayPlans) return;

    const today = stateManager.getTodayDate();
    if (!state.DayPlans[today]) {
      state.DayPlans[today] = {
        id: today,
        date: today,
        day_type: state.Settings?.defaultDayType || 'A',
        time_blocks: [],
        baseline_goal: { text: '', completed: false },
        stretch_goal: { text: block.stretch || '', completed: false },
        routines_completed: {},
        notes: '',
        rating: 0,
      };
    }

    const plan = state.DayPlans[today];
    const newBlock = {
      id: `tb-${Date.now()}`,
      time: '09:00',
      title: `Deep Block: ${block.focus} (C${block.cluster_id})`,
      completed: false,
    };

    plan.time_blocks = plan.time_blocks || [];
    plan.time_blocks.push(newBlock);
    stateManager.saveToStorage();

    // Re-render if on Daily screen
    if (state.screen === 'Daily') {
      render();
    }
  },
};

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = StrategicRouter;
}
