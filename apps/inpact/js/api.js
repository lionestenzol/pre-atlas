// inPACT Atlas API Client
// Connects to delta-kernel (port 3001) for state sync and governance data.
// Offline-first: all methods return null/false on failure, never throw.

const AtlasAPI = {
  baseUrl: 'http://localhost:3001',
  token: null,
  online: false,
  lastSyncAt: null,
  lastSyncOk: false,

  async init() {
    const url = (typeof state !== 'undefined' && state.Settings && state.Settings.atlasApiUrl)
      ? state.Settings.atlasApiUrl
      : this.baseUrl;
    this.baseUrl = url;

    const health = await this._fetch('/api/health');
    this.online = !!(health && health.ok !== false);

    if (this.online) {
      const auth = await this._fetch('/api/auth/token');
      if (auth && auth.token) {
        this.token = auth.token;
      }
    }

    return this.online;
  },

  async _fetch(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    const headers = {};
    if (this.token) headers['Authorization'] = 'Bearer ' + this.token;
    if (options.body) headers['Content-Type'] = 'application/json';

    try {
      const res = await fetch(this.baseUrl + path, {
        ...options,
        headers: { ...headers, ...(options.headers || {}) },
        signal: controller.signal,
      });
      clearTimeout(timeout);

      if (!res.ok) {
        console.warn('[AtlasAPI] ' + res.status + ' on ' + path);
        return null;
      }

      return await res.json();
    } catch (e) {
      clearTimeout(timeout);
      if (e.name !== 'AbortError') {
        console.warn('[AtlasAPI] fetch failed:', path, e.message);
      }
      return null;
    }
  },

  // CycleBoard state (inPACT's full state blob)

  async getCycleBoardState() {
    const res = await this._fetch('/api/cycleboard');
    if (res && res.ok && res.data) return res.data;
    return null;
  },

  async putCycleBoardState(stateBlob) {
    const res = await this._fetch('/api/cycleboard', {
      method: 'PUT',
      body: JSON.stringify(stateBlob),
    });
    const ok = !!(res && res.ok);
    this.lastSyncOk = ok;
    if (ok) this.lastSyncAt = new Date().toISOString();
    return ok;
  },

  // Read-only governance data

  async getUnifiedState() {
    return await this._fetch('/api/state/unified');
  },

  async getDailyBrief() {
    return await this._fetch('/api/daily-brief');
  },

  async getSignals() {
    return await this._fetch('/api/signals');
  },

  async getHealth() {
    const res = await this._fetch('/api/health');
    this.online = !!(res && res.ok !== false);
    return this.online;
  },
};
