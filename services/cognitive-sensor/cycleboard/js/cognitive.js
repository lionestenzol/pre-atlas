// CycleBoard Cognitive Controller Module
// Brain Integration for cognitive state management

// Shared staleness utility for all brain data consumers
const DataFreshness = {
  check(dateString, thresholdHours = 24) {
    if (!dateString) {
      return { stale: true, ageHours: -1, ageText: 'age unknown' };
    }
    const ageMs = Date.now() - new Date(dateString).getTime();
    const ageHours = Math.floor(ageMs / (1000 * 60 * 60));
    const mins = Math.floor(ageMs / 60000);
    let ageText;
    if (mins < 1) ageText = 'just now';
    else if (mins < 60) ageText = `${mins}m ago`;
    else if (ageHours < 24) ageText = `${ageHours}h ago`;
    else if (ageHours < 48) ageText = 'yesterday';
    else ageText = `${Math.floor(ageHours / 24)} days ago`;
    return { stale: ageHours >= thresholdHours || ageHours < 0, ageHours, ageText };
  }
};

const CognitiveController = {
  payload: null,
  dailyPayload: null,
  buildAllowed: true,
  bannerVisible: true,
  initialized: false,
  error: null,
  freshness: null,
  directiveText: null,

  _pollTimer: null,

  async init() {
    if (this.initialized) return;
    await this._loadData(true);
  },

  // Delta-kernel API base (configurable for standalone vs embedded)
  _apiBase: 'http://localhost:3001',

  _authHeaders() {
    const h = {};
    if (typeof stateManager !== 'undefined' && stateManager.apiKey) {
      h['Authorization'] = `Bearer ${stateManager.apiKey}`;
    }
    return h;
  },

  async _loadData(isFirstLoad) {
    try {
      // Primary: load unified state from delta-kernel API
      const response = await fetch(`${this._apiBase}/api/state/unified`, {
        headers: this._authHeaders(),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const unified = await response.json();

      if (!unified || !unified.ok) {
        throw new Error('Invalid unified state response');
      }

      // Map unified response to the shape CycleBoard expects
      const newPayload = unified.cognitive?.cognitive_state || {};
      let newDailyPayload = unified.cognitive?.today || null;

      // Enrich with derived values from unified endpoint
      if (!newDailyPayload) {
        newDailyPayload = {
          build_allowed: unified.derived?.build_allowed ?? true,
          generated_at: unified.ts,
        };
      }

      // Load daily directive text (still from file — not in API yet)
      let newDirective = null;
      try {
        const dtResp = await fetch('brain/daily_directive.txt');
        if (dtResp.ok) {
          newDirective = await dtResp.text();
        }
      } catch (_) {}

      // On refresh: skip re-render if data hasn't changed
      const newTimestamp = unified.ts || newDailyPayload?.generated_at || newPayload?.generated_at;
      const oldTimestamp = this.dailyPayload?.generated_at || this.payload?.generated_at;
      if (!isFirstLoad && newTimestamp && oldTimestamp && newTimestamp === oldTimestamp) {
        return; // No change
      }

      this.payload = newPayload;
      this.dailyPayload = newDailyPayload;
      this.buildAllowed = unified.derived?.build_allowed !== false;
      this.directiveText = newDirective;
      this.initialized = true;
      this.error = null;
      this.freshness = DataFreshness.check(newTimestamp);

      // Store unified derived data for Command screen
      this.unified = unified.derived || {};

      this.applyGovernance();

      if (typeof render === 'function') render();

    } catch (error) {
      this.error = error.message;
      this.initialized = true;

      if (error.message.includes('HTTP 404') || error.message === 'HTTP 404: Not Found') {
        if (isFirstLoad) console.log('Cognitive system offline. Run: python refresh.py');
      } else {
        console.warn('Cognitive system error:', error.message);
      }
      this.showOfflineState();
    }
  },

  async refresh() {
    await this._loadData(false);
    await StrategicRouter.refresh();
  },

  startPolling() {
    if (this._pollTimer) return;
    this._pollTimer = setInterval(() => this.refresh(), 30000);

    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        clearInterval(this._pollTimer);
        this._pollTimer = null;
      } else {
        this.refresh();
        this._pollTimer = setInterval(() => this.refresh(), 30000);
      }
    });
  },

  stopPolling() {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
  },

  showOfflineState() {
    const banner = document.getElementById('cognitive-directive');
    const indicator = document.getElementById('cognitive-indicator');
    const indicatorDot = document.getElementById('cognitive-indicator-dot');
    const onlineMsg = document.getElementById('cognitive-online-msg');
    const offlineMsg = document.getElementById('cognitive-offline-msg');

    if (!banner) return;

    // Show banner with offline content
    banner.className = 'w-full shadow-lg';
    banner.style.position = 'sticky';
    banner.style.top = '0';
    banner.style.zIndex = '50';
    banner.style.display = 'block';

    if (onlineMsg) onlineMsg.style.display = 'none';
    if (offlineMsg) offlineMsg.style.display = 'block';

    // Show indicator dot in gray
    if (indicatorDot) {
      indicatorDot.className = 'w-4 h-4 rounded-full animate-pulse shadow-lg bg-gray-500';
    }
    if (indicator) indicator.style.display = 'none';
  },

  async retry() {
    this.initialized = false;
    this.error = null;
    this.payload = null;
    await this._loadData(true);
  },

  applyGovernance() {
    if (!this.payload) return;

    // Calculate mode from payload
    const closureData = this.payload.closure || {};
    const mode = closureData.ratio < 15 ? 'CLOSURE' :
                 closureData.open > 10 ? 'MAINTENANCE' : 'BUILD';
    const risk = closureData.ratio < 15 ? 'HIGH' :
                 closureData.open > 10 ? 'MEDIUM' : 'LOW';

    // Store for other functions
    this.mode = mode;
    this.risk = risk;

    // Show and update banner
    this.updateDirectiveBanner(mode, risk, closureData);

    // Apply mode-specific policies
    if (mode === 'CLOSURE') {
      this.enforceClosure();
    }

    // Apply risk indicators
    this.applyRiskIndicators(risk);
  },

  updateDirectiveBanner(mode, risk, closureData) {
    const banner = document.getElementById('cognitive-directive');
    const indicator = document.getElementById('cognitive-indicator');
    const indicatorDot = document.getElementById('cognitive-indicator-dot');
    const onlineMsg = document.getElementById('cognitive-online-msg');
    const offlineMsg = document.getElementById('cognitive-offline-msg');

    if (!banner) return;

    // Show online content, hide offline
    if (onlineMsg) onlineMsg.style.display = 'block';
    if (offlineMsg) offlineMsg.style.display = 'none';

    // Update content
    document.getElementById('directive-mode').textContent = mode;
    document.getElementById('directive-risk').textContent = risk;
    document.getElementById('directive-loops').textContent = closureData.open || '--';

    const topLoop = this.payload.loops?.[0]?.title || 'No loops detected';
    const action = mode === 'CLOSURE' ? `Close or archive: ${topLoop}` :
                   mode === 'MAINTENANCE' ? `Review: ${topLoop}` :
                   'Focus on creation today';
    document.getElementById('directive-action').textContent = action;

    // Staleness warning
    if (this.freshness?.stale) {
      const actionEl = document.getElementById('directive-action');
      if (actionEl) {
        actionEl.insertAdjacentHTML('afterend',
          `<div class="text-xs mt-1 opacity-75"><i class="fas fa-clock mr-1"></i>Data ${this.freshness.ageText}</div>`);
      }
    }

    // Color-code by mode
    const colors = {
      'CLOSURE': 'bg-gradient-to-r from-red-600 to-orange-600',
      'MAINTENANCE': 'bg-gradient-to-r from-yellow-600 to-amber-600',
      'BUILD': 'bg-gradient-to-r from-green-600 to-emerald-600'
    };

    const dotColors = {
      'CLOSURE': 'bg-red-500',
      'MAINTENANCE': 'bg-yellow-500',
      'BUILD': 'bg-green-500'
    };

    banner.className = `w-full text-white shadow-lg ${colors[mode]}`;
    banner.style.position = 'sticky';
    banner.style.top = '0';
    banner.style.zIndex = '50';

    if (indicatorDot) {
      indicatorDot.className = `w-4 h-4 rounded-full animate-pulse shadow-lg ${dotColors[mode]}`;
    }

    // Show banner
    banner.style.display = 'block';
    if (indicator) indicator.style.display = 'none';
  },

  enforceClosure() {
    if (this.buildAllowed) return;

    // Disable all create/add buttons
    const createSelectors = [
      'button[onclick*="openCreateModal"]',
      'button[onclick*="addFocusTask"]',
      'button[onclick*="createFocusTask"]',
      'button[onclick*="createTask"]',
    ];

    createSelectors.forEach(sel => {
      document.querySelectorAll(sel).forEach(btn => {
        btn.disabled = true;
        btn.classList.add('governance-locked');
        btn.title = 'Creation locked — close loops first';
      });
    });

    // Add lock overlay to main content area
    const existing = document.getElementById('governance-lock-banner');
    if (!existing) {
      const lockBanner = document.createElement('div');
      lockBanner.id = 'governance-lock-banner';
      lockBanner.className = 'governance-lock-banner';
      lockBanner.innerHTML = '<i class="fas fa-lock mr-2"></i> Creation locked — close or archive open loops to unlock BUILD mode';
      const main = document.getElementById('main-content') || document.querySelector('main');
      if (main) main.prepend(lockBanner);
    }
  },

  /**
   * Gate check — call before any creation action.
   * Returns true if creation is allowed, false if blocked.
   */
  canCreate() {
    if (this.buildAllowed) return true;
    UI.showToast('Creation Locked', 'Close or archive open loops before creating new tasks.', 'error');
    return false;
  },

  applyRiskIndicators(risk) {
    // Add risk badge to sidebar if not exists
    const sidebar = document.getElementById('sidebar');
    if (sidebar && !document.getElementById('cognitive-risk-badge')) {
      const badge = document.createElement('div');
      badge.id = 'cognitive-risk-badge';
      badge.className = `mx-4 mb-4 px-3 py-2 rounded-lg text-center text-sm font-bold ${
        risk === 'HIGH' ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' :
        risk === 'MEDIUM' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300' :
        'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
      }`;
      badge.innerHTML = `<i class="fas fa-brain mr-1"></i> ${risk} RISK`;
      sidebar.insertBefore(badge, sidebar.firstChild);
    }
  },

  getMode() {
    return this.mode || 'OFFLINE';
  },

  getRisk() {
    return this.risk || 'UNKNOWN';
  },

  getOpenLoops() {
    return this.payload?.loops || [];
  },

  isClosureMode() {
    return this.mode === 'CLOSURE';
  }
};

function toggleCognitiveBanner() {
  const banner = document.getElementById('cognitive-directive');
  const indicator = document.getElementById('cognitive-indicator');

  if (banner.style.display !== 'none') {
    banner.style.display = 'none';
    indicator.style.display = 'block';
  } else {
    banner.style.display = 'block';
    indicator.style.display = 'none';
  }
}

function openControlPanel() {
  if (window !== window.parent) {
    window.parent.postMessage({ type: 'atlas-navigate', target: 'control' }, '*');
  } else {
    window.open('../control_panel.html', '_blank');
  }
}

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = CognitiveController;
}
