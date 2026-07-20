// inPACT Google Calendar Sync Module
// Browser-side integration via Google Identity Services (gsi) + gapi

const CalendarSync = (() => {
  const SCOPES = 'https://www.googleapis.com/auth/calendar.events';
  const DISCOVERY_DOC = 'https://www.googleapis.com/discovery/v1/apis/calendar/v3/rest';
  const TOKEN_KEY = 'inpact-gcal-token';
  const TOKEN_EXPIRY_BUFFER_MS = 60000;
  const CALENDAR_ID = '7770736e5f8aa82b297209089ff8e02111d5256854d4a40ceb21a09a199d7800@group.calendar.google.com';
  // Local map of our event keys -> Google event IDs, namespaced by date:
  // { "2026-07-20": { "block:<id>": "<googleEventId>", ... } }. This is what
  // makes sync push-based and idempotent: a re-sync PATCHes the existing
  // event instead of INSERTing a duplicate, and removes events we dropped.
  const EVENT_MAP_KEY = 'inpact-gcal-event-map';

  let tokenClient = null;
  let gapiInited = false;
  let gisInited = false;
  let clientId = null;

  function getClientId() {
    if (clientId) return clientId;
    clientId = localStorage.getItem('inpact-gcal-client-id');
    return clientId;
  }

  function setClientId(id) {
    clientId = id;
    localStorage.setItem('inpact-gcal-client-id', id);
  }

  function isConfigured() {
    return !!getClientId();
  }

  function isReady() {
    return gapiInited && gisInited && isConfigured();
  }

  function getStoredToken() {
    try {
      const raw = localStorage.getItem(TOKEN_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  function saveToken(resp) {
    const expiresInMs = Number(resp.expires_in || 3600) * 1000;
    localStorage.setItem(TOKEN_KEY, JSON.stringify({
      access_token: resp.access_token,
      expires_at: Date.now() + expiresInMs - TOKEN_EXPIRY_BUFFER_MS,
    }));
  }

  function clearStoredToken() {
    localStorage.removeItem(TOKEN_KEY);
  }

  function getEventMap() {
    try {
      const raw = localStorage.getItem(EVENT_MAP_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  }

  function saveEventMap(map) {
    localStorage.setItem(EVENT_MAP_KEY, JSON.stringify(map));
  }

  // Token validity is tracked in our own storage (with expiry) rather than
  // trusting gapi's in-memory state, since that resets on every page load.
  function hasToken() {
    const stored = getStoredToken();
    return !!stored && stored.expires_at > Date.now();
  }

  function restoreToken() {
    const stored = getStoredToken();
    if (stored && stored.expires_at > Date.now()) {
      gapi.client.setToken({ access_token: stored.access_token });
    } else if (stored) {
      clearStoredToken();
    }
  }

  async function loadGapi() {
    if (gapiInited) return;
    await new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://apis.google.com/js/api.js';
      script.onload = resolve;
      script.onerror = () => reject(new Error('Failed to load Google API'));
      document.head.appendChild(script);
    });
    await new Promise((resolve, reject) => {
      gapi.load('client', { callback: resolve, onerror: reject });
    });
    await gapi.client.init({ discoveryDocs: [DISCOVERY_DOC] });
    gapiInited = true;
  }

  async function loadGis() {
    if (gisInited) return;
    await new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.onload = resolve;
      script.onerror = () => reject(new Error('Failed to load Google Identity Services'));
      document.head.appendChild(script);
    });
    gisInited = true;
  }

  async function init() {
    if (!isConfigured()) return;
    await Promise.all([loadGapi(), loadGis()]);
    restoreToken();
    tokenClient = google.accounts.oauth2.initTokenClient({
      client_id: getClientId(),
      scope: SCOPES,
      callback: () => {},
    });
  }

  // The silent-refresh win comes from hasToken(): while a stored token is
  // still valid, syncToday never calls authorize() at all, so no popup.
  // Once it's expired we DO need Google, and the request must fire
  // synchronously inside the triggering click gesture — opening the consent
  // popup from an async callback gets blocked by the browser. So we request
  // consent directly here rather than doing a silent-then-fallback dance.
  function authorize() {
    return new Promise((resolve, reject) => {
      if (!tokenClient) {
        reject(new Error('Calendar not initialized. Set your Google Client ID first.'));
        return;
      }
      tokenClient.callback = (resp) => {
        if (resp.error) {
          reject(new Error(resp.error));
          return;
        }
        saveToken(resp);
        resolve(resp);
      };
      tokenClient.requestAccessToken({ prompt: hasToken() ? '' : 'consent' });
    });
  }

  // A block titled "Morning Routine" etc. matches a Routine template
  // (_findRoutineMatch, defined in screens.js) and expands into one event
  // per step instead of a single block event, so each step gets its own
  // real time on the calendar rather than being collapsed into an hour.
  function buildTimeBlockEvents(dateStr, timeBlocks) {
    const routines = (typeof stateManager !== 'undefined' && stateManager.state?.Routine) || {};
    const findRoutine = typeof _findRoutineMatch === 'function' ? _findRoutineMatch : () => null;
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const events = [];

    // Template blocks (the fallback when no day plan exists) have no id, so
    // fall back to a title+time key. Both are stable enough to map an event
    // to the same Google entry across re-syncs.
    const blockKey = block => `block:${block.id || `${block.title}@${block.time}`}`;

    for (const block of timeBlocks) {
      const routineName = findRoutine(block.title);
      const steps = routineName ? routines[routineName] : null;

      if (steps && steps.length) {
        let cursor = parseInpactTime(dateStr, block.time);
        steps.forEach((step, idx) => {
          const duration = step.duration || 5;
          const startDt = new Date(cursor);
          const endDt = new Date(startDt.getTime() + duration * 60000);
          events.push({
            _key: `step:${block.id || block.title}:${idx}`,
            summary: `${block.title}: ${step.text}`,
            description: `inPACT routine step${block.completed ? ' [DONE]' : ''}`,
            start: { dateTime: toLocalISO(startDt), timeZone: tz },
            end: { dateTime: toLocalISO(endDt), timeZone: tz },
            colorId: block.completed ? '2' : '11',
          });
          cursor = endDt;
        });
      } else {
        const startDt = parseInpactTime(dateStr, block.time);
        const endDt = new Date(startDt.getTime() + (block.duration || 30) * 60000);
        events.push({
          _key: blockKey(block),
          summary: block.title,
          description: `inPACT time block${block.completed ? ' [DONE]' : ''}`,
          start: { dateTime: toLocalISO(startDt), timeZone: tz },
          end: { dateTime: toLocalISO(endDt), timeZone: tz },
          colorId: block.completed ? '2' : '11',
        });
      }
    }

    return events;
  }

  function parseInpactTime(dateStr, timeStr) {
    const match = timeStr.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
    if (!match) {
      const [h, m] = timeStr.split(':').map(Number);
      return new Date(`${dateStr}T${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00`);
    }
    let hours = parseInt(match[1]);
    const minutes = parseInt(match[2]);
    const ampm = match[3].toUpperCase();
    if (ampm === 'PM' && hours !== 12) hours += 12;
    if (ampm === 'AM' && hours === 12) hours = 0;
    return new Date(`${dateStr}T${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:00`);
  }

  function toLocalISO(date) {
    const off = date.getTimezoneOffset();
    const local = new Date(date.getTime() - off * 60000);
    return local.toISOString().slice(0, 19);
  }

  async function syncToday() {
    if (!isReady()) {
      await promptSetup();
      return;
    }

    if (!hasToken()) {
      await authorize();
    }

    const state = typeof stateManager !== 'undefined' ? stateManager.state : undefined;
    if (!state) throw new Error('No inPACT state found');

    const today = new Date();
    const dateStr = today.toISOString().slice(0, 10);
    const plan = state.DayPlans?.[dateStr];
    const dayType = plan?.day_type || state.Settings?.defaultDayType || 'A';
    const timeBlocks = plan?.time_blocks || state.DayTypeTemplates?.[dayType]?.timeBlocks || [];

    if (!timeBlocks.length) {
      UI.showToast('No Blocks', 'No time blocks found for today.', 'info');
      return;
    }

    const events = buildTimeBlockEvents(dateStr, timeBlocks);

    // Push-based, idempotent sync keyed off the local event map. For each
    // event we PATCH the existing Google entry if we've synced it before,
    // otherwise INSERT and remember its id. Anything in the map for today
    // that this sync no longer produces gets DELETEd. No GET/polling.
    const map = getEventMap();
    const dayMap = map[dateStr] || {};
    const seenKeys = new Set();
    let created = 0, updated = 0, deleted = 0;
    const errors = [];

    for (const event of events) {
      const key = event._key;
      seenKeys.add(key);
      const resource = { ...event };
      delete resource._key;

      const existingId = dayMap[key];
      try {
        if (existingId) {
          try {
            await gapi.client.calendar.events.patch({
              calendarId: CALENDAR_ID, eventId: existingId, resource,
            });
            updated++;
          } catch (err) {
            // Event was deleted on Google's side (404/410) — re-create it.
            if (err.status === 404 || err.status === 410) {
              const resp = await gapi.client.calendar.events.insert({ calendarId: CALENDAR_ID, resource });
              dayMap[key] = resp.result.id;
              created++;
            } else {
              throw err;
            }
          }
        } else {
          const resp = await gapi.client.calendar.events.insert({ calendarId: CALENDAR_ID, resource });
          dayMap[key] = resp.result.id;
          created++;
        }
      } catch (err) {
        errors.push(`${event.summary}: ${err.result?.error?.message || err.message}`);
      }
    }

    // Remove events we previously synced for today but no longer have.
    for (const key of Object.keys(dayMap)) {
      if (seenKeys.has(key)) continue;
      try {
        await gapi.client.calendar.events.delete({ calendarId: CALENDAR_ID, eventId: dayMap[key] });
        deleted++;
      } catch (err) {
        // Already gone on Google's side is fine; anything else we log.
        if (err.status !== 404 && err.status !== 410) {
          errors.push(`delete ${key}: ${err.result?.error?.message || err.message}`);
        }
      }
      delete dayMap[key];
    }

    map[dateStr] = dayMap;
    saveEventMap(map);

    const summary = [
      created ? `${created} added` : '',
      updated ? `${updated} updated` : '',
      deleted ? `${deleted} removed` : '',
    ].filter(Boolean).join(', ') || 'No changes';

    if (errors.length) {
      UI.showToast('Partial Sync', `${summary}; ${errors.length} failed.`, 'warning');
    } else {
      UI.showToast('Calendar Synced', `${summary}.`, 'success');
    }
  }

  function promptSetup() {
    const content = `
      <div style="padding:1.5rem;max-width:28rem;">
        <h2 style="font-size:1.125rem;font-weight:700;margin-bottom:1rem;">Google Calendar Setup</h2>
        <p style="font-size:0.875rem;color:var(--ip-gray-600);margin-bottom:1rem;">
          To sync your inPACT schedule with Google Calendar, you need a Google Cloud OAuth Client ID.
        </p>
        <ol style="font-size:0.8125rem;color:var(--ip-gray-600);margin-bottom:1rem;padding-left:1.25rem;list-style:decimal;">
          <li>Go to <a href="https://console.cloud.google.com/apis/credentials" target="_blank" style="color:var(--ip-blue-600);text-decoration:underline;">Google Cloud Console</a></li>
          <li>Create or select a project</li>
          <li>Enable the Google Calendar API</li>
          <li>Create an OAuth 2.0 Client ID (Web application)</li>
          <li>Add <code style="background:var(--ip-gray-100);padding:0.125rem 0.25rem;border-radius:0.25rem;">http://localhost:3006</code> as an authorized JavaScript origin</li>
          <li>Copy the Client ID below</li>
        </ol>
        <input id="gcal-client-id-input" type="text" placeholder="your-client-id.apps.googleusercontent.com"
          style="width:100%;padding:0.625rem;border:1px solid var(--ip-gray-300);border-radius:0.375rem;font-size:0.8125rem;margin-bottom:1rem;"
          value="${getClientId() || ''}" />
        <div style="display:flex;gap:0.5rem;justify-content:flex-end;">
          <button onclick="document.getElementById('modal-container').innerHTML=''" class="td-btn-ghost">Cancel</button>
          <button onclick="CalendarSync.saveSetup()" class="td-btn-pill active" style="padding:0.625rem 1.25rem;">Save and Connect</button>
        </div>
      </div>
    `;
    UI.showModal(content);
  }

  async function saveSetup() {
    const input = document.getElementById('gcal-client-id-input');
    const id = input?.value?.trim();
    if (!id || !id.includes('.apps.googleusercontent.com')) {
      UI.showToast('Invalid ID', 'Paste a valid Google OAuth Client ID.', 'error');
      return;
    }
    setClientId(id);
    document.getElementById('modal-container').innerHTML = '';
    UI.showToast('Saved', 'Google Client ID saved. Connecting...', 'info');
    try {
      await init();
      await authorize();
      UI.showToast('Connected', 'Google Calendar connected.', 'success');
    } catch (err) {
      UI.showToast('Auth Failed', err.message, 'error');
    }
  }

  function disconnect() {
    if (gapi?.client?.getToken()) {
      google.accounts.oauth2.revoke(gapi.client.getToken().access_token);
      gapi.client.setToken(null);
    }
    clearStoredToken();
    UI.showToast('Disconnected', 'Google Calendar disconnected.', 'info');
  }

  function renderSyncButton() {
    const connected = isReady() && hasToken();
    return `
      <button onclick="CalendarSync.syncToday()" class="td-btn-pill" style="padding:0.5rem 1rem;font-size:0.8125rem;display:inline-flex;align-items:center;gap:0.375rem;">
        <i class="fas fa-calendar-plus" style="font-size:0.75rem;"></i>
        ${connected ? 'Sync to Calendar' : 'Connect Google Calendar'}
      </button>
    `;
  }

  // Auto-init if client ID is already saved
  if (isConfigured()) {
    init().catch(() => {});
  }

  return {
    init,
    authorize,
    syncToday,
    promptSetup,
    saveSetup,
    disconnect,
    isConfigured,
    isReady,
    hasToken,
    renderSyncButton,
    setClientId,
  };
})();
