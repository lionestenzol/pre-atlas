// CycleBoard App Initialization
// Main entry point that initializes all modules

// Initialize state manager (global)
const stateManager = new CycleBoardState();

// ── Cross-view navigation ──
// Works both embedded in atlas_boot.html (postMessage) and standalone (window.open)
const AtlasNav = {
  isEmbedded: window !== window.parent,

  viewUrls: {
    control: '/cognitive-sensor/control_panel.html',
    atlas: '/cognitive-sensor/cognitive_atlas.html',
    ideas: '/cognitive-sensor/idea_dashboard.html',
    docs: '/cognitive-sensor/docs_viewer.html',
    aegis: '../../aegis-fabric/src/ui/dashboard.html',
    timeline: '../../delta-kernel/src/ui/timeline.html',
    boot: '../../../atlas_boot.html',
  },

  // Tab names as atlas_boot.html knows them
  tabNames: {
    control: 'Control Panel',
    atlas: 'Cognitive Atlas',
    docs: 'Docs',
    aegis: 'Aegis',
  },

  open(target) {
    if (this.isEmbedded) {
      // Switch tab in parent atlas_boot.html
      window.parent.postMessage({ type: 'atlas-navigate', target }, '*');
    } else {
      const url = this.viewUrls[target];
      if (url) window.open(url, '_blank');
    }
  },
};

// ── Brain data store (loaded async, available to all screens) ──
const BrainData = {
  ideaRegistry: null,
  governanceState: null,
  governorHeadline: null,
  lifeSignals: null,
  energyMetrics: null,
  financeMetrics: null,
  skillsMetrics: null,
  networkMetrics: null,
  osintFeed: null,
  weeklyPlan: null,

  _apiBase: 'http://localhost:3001',

  async load() {
    // Try API first, fall back to local files
    const apiSources = [
      { key: 'ideaRegistry', url: `${this._apiBase}/api/ideas`, fallback: 'brain/idea_registry.json' },
      { key: 'governanceState', url: `${this._apiBase}/api/governance/config`, fallback: 'brain/governance_state.json' },
      { key: 'governorHeadline', url: null, fallback: 'brain/governor_headline.json' },
      { key: 'energyMetrics', url: null, fallback: 'brain/energy_metrics.json' },
      { key: 'financeMetrics', url: null, fallback: 'brain/finance_metrics.json' },
      { key: 'skillsMetrics', url: null, fallback: 'brain/skills_metrics.json' },
      { key: 'networkMetrics', url: null, fallback: 'brain/network_metrics.json' },
      { key: 'osintFeed', url: null, fallback: 'brain/osint_feed.json' },
      { key: 'weeklyPlan', url: null, fallback: 'brain/weekly_plan.json' },
    ];
    const authHeaders = {};
    if (typeof stateManager !== 'undefined' && stateManager.apiKey) {
      authHeaders['Authorization'] = `Bearer ${stateManager.apiKey}`;
    }
    await Promise.allSettled(apiSources.map(async ({ key, url, fallback }) => {
      try {
        if (url) {
          const res = await fetch(url, { headers: authHeaders });
          if (res.ok) {
            const data = await res.json();
            this[key] = data.data || data;
            return;
          }
        }
        // Fallback to local file
        const res = await fetch(fallback);
        if (res.ok) this[key] = await res.json();
      } catch (_) {}
    }));
  },

  getTopIdeas(limit = 3) {
    if (!this.ideaRegistry) return [];
    return (this.ideaRegistry.execute_now || []).slice(0, limit);
  },

  getNextUpIdeas(limit = 5) {
    if (!this.ideaRegistry) return [];
    return (this.ideaRegistry.next_up || []).slice(0, limit);
  },

  getDriftScore() {
    return this.governorHeadline?.drift_score ?? null;
  },

  getDriftAlerts() {
    return this.governorHeadline?.drift_alerts || [];
  },

  getComplianceRate() {
    return this.governorHeadline?.compliance_rate ?? null;
  },

  getLastRefresh() {
    return this.governorHeadline?.generated_at || null;
  },

  getTopMove() {
    return this.governorHeadline?.top_move || null;
  },

  getWarning() {
    return this.governorHeadline?.warning || null;
  },

  getEnergyLevel() {
    return this.energyMetrics?.energy_level ?? 50;
  },
  getMentalLoad() {
    return this.energyMetrics?.mental_load ?? 5;
  },
  getBurnoutRisk() {
    return this.energyMetrics?.burnout_risk ?? false;
  },
  getRedAlertActive() {
    return this.energyMetrics?.red_alert_active ?? false;
  },
  getRunwayMonths() {
    return this.financeMetrics?.runway_months ?? 3;
  },
  getMoneyDelta() {
    return this.financeMetrics?.money_delta ?? 0;
  },
  getSkillsUtilization() {
    return this.skillsMetrics?.utilization_pct ?? 50;
  },
  getNetworkScore() {
    return this.networkMetrics?.collaboration_score ?? 30;
  },
  getLifePhase() {
    return this.energyMetrics?.life_phase ?? this.governanceState?.life_phase ?? 1;
  },
  getLifePhaseName() {
    const names = { 1: 'Stabilization', 2: 'Leverage', 3: 'Extraction', 4: 'Scaling', 5: 'Generational' };
    return names[this.getLifePhase()] || 'Unknown';
  },
};

const ServiceHealthBar = {
  _intervalId: null,
  _pollMs: 60000,
  _serviceIds: ['delta', 'uasc', 'cortex'],

  async init() {
    await this.refresh();
    this._intervalId = window.setInterval(() => this.refresh(), this._pollMs);
  },

  async refresh() {
    const [payloadResult, healthResult] = await Promise.allSettled([
      this.loadDailyPayload(),
      this.checkAllServices(),
    ]);

    if (payloadResult.status === 'fulfilled') this.updatePayload(payloadResult.value);
    else this.updatePayload(null);
  },

  async loadDailyPayload() {
    const response = await fetch('brain/daily_payload.json', { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`Failed to load daily payload: ${response.status}`);
    }
    return response.json();
  },

  async checkAllServices() {
    try {
      const response = await fetch('/api/services/health', { cache: 'no-store' });
      if (!response.ok) throw new Error('Health endpoint failed');
      const data = await response.json();
      for (const id of this._serviceIds) {
        const dot = document.getElementById('health-dot-' + id);
        if (dot) this.setServiceState(dot, data[id]?.status === 'up');
      }
    } catch (_) {
      for (const id of this._serviceIds) {
        const dot = document.getElementById('health-dot-' + id);
        if (dot) this.setServiceState(dot, false);
      }
    }
  },

  setServiceState(dot, isUp) {
    dot.classList.toggle('service-health-dot--up', isUp);
    dot.classList.toggle('service-health-dot--down', !isUp);
  },

  updatePayload(payload) {
    const lastRefreshEl = document.getElementById('health-last-refresh');
    const modeEl = document.getElementById('health-mode');
    const directiveEl = document.getElementById('health-directive');
    if (!lastRefreshEl || !modeEl || !directiveEl) return;

    const timestamp = payload?.generated_at || payload?.pipeline_ts || null;
    const directive = payload?.directive || payload?.primary_action || 'No directive available';

    lastRefreshEl.textContent = this.formatTimestamp(timestamp);
    modeEl.textContent = payload?.mode || '--';
    directiveEl.textContent = directive;
    directiveEl.title = directive;
  },

  formatTimestamp(value) {
    if (!value) return '--';

    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toLocaleString();
    }

    return value;
  },
};

// State accessor - always returns current stateManager.state
// Use this instead of caching state reference to avoid sync issues
Object.defineProperty(window, 'state', {
  get() { return stateManager.state; },
  set(value) {
    // When setting state, merge into stateManager.state
    Object.keys(stateManager.state).forEach(key => delete stateManager.state[key]);
    Object.assign(stateManager.state, value);
  },
  configurable: true
});

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  // Always apply dark mode (matches atlas boot theme)
  document.documentElement.classList.add('dark');
  if (state.Settings) state.Settings.darkMode = true;

  // Initialize main app
  init();
  ServiceHealthBar.init();

  // Load API key first, then initialize everything that needs it
  stateManager.loadApiKey().then(() => {
    // Load state from API (non-blocking — re-renders if API has newer data)
    stateManager.loadFromApi().then(loaded => { if (loaded) render(); });

    // Initialize cognitive controller + start auto-refresh polling
    CognitiveController.init().then(() => CognitiveController.startPolling());

    // Load additional brain data (ideas, governance, headline)
    BrainData.load().then(() => { if (typeof render === 'function') render(); });
  });

  // Initialize strategic leverage router (no API key needed)
  StrategicRouter.init();
});
