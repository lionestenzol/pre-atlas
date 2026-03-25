// CycleBoard Cognitive Controller Module
// Brain Integration for cognitive state management

const CognitiveController = {
  payload: null,
  dailyPayload: null,
  buildAllowed: true,
  bannerVisible: true,
  initialized: false,
  error: null,

  async init() {
    // Prevent multiple initializations
    if (this.initialized) return;

    try {
      // Try to load cognitive state from workspace
      const response = await fetch('cognitive_state.json');

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        throw new Error('Invalid content type: expected JSON');
      }

      const text = await response.text();
      if (!text.trim()) {
        throw new Error('Empty response');
      }

      try {
        this.payload = JSON.parse(text);
      } catch (parseError) {
        throw new Error(`JSON parse error: ${parseError.message}`);
      }

      // Validate payload structure
      if (!this.payload || typeof this.payload !== 'object') {
        throw new Error('Invalid payload structure');
      }

      // Also load daily_payload.json for build_allowed signal
      try {
        const dpResp = await fetch('brain/daily_payload.json');
        if (dpResp.ok) {
          this.dailyPayload = await dpResp.json();
          this.buildAllowed = this.dailyPayload.build_allowed !== false;
        }
      } catch (_) {
        // daily_payload not available — default to allowed
      }

      this.initialized = true;
      this.error = null;
      this.applyGovernance();

    } catch (error) {
      this.error = error.message;
      this.initialized = true; // Mark as initialized even on error to prevent retries

      // Only log in development or if it's an unexpected error
      if (error.message.includes('HTTP 404') || error.message === 'HTTP 404: Not Found') {
        console.log('Cognitive system offline. Banner hidden. Run: python refresh.py');
      } else {
        console.warn('Cognitive system error:', error.message);
      }
      // Keep banner hidden if no cognitive data
    }
  },

  // Allow manual retry
  async retry() {
    this.initialized = false;
    this.error = null;
    this.payload = null;
    await this.init();
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

    if (!banner) return;

    // Update content
    document.getElementById('directive-mode').textContent = mode;
    document.getElementById('directive-risk').textContent = risk;
    document.getElementById('directive-loops').textContent = closureData.open || '--';

    const topLoop = this.payload.loops?.[0]?.title || 'No loops detected';
    const action = mode === 'CLOSURE' ? `Close or archive: ${topLoop}` :
                   mode === 'MAINTENANCE' ? `Review: ${topLoop}` :
                   'Focus on creation today';
    document.getElementById('directive-action').textContent = action;

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
