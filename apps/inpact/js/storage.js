// inPACT Storage Abstraction
//
// A StorageAdapter isolates *where* state bytes live from *what* they mean.
// The app (CycleBoardState) owns parsing, migration, and history; adapters own
// nothing but persistence. This is the single seam we widen to add cloud sync:
// LocalStorageAdapter is the current behavior; a SupabaseAdapter will be a
// second implementation swapped in after sign-in (see SPEC_MVP_36H.md, block D).
//
// Contract (duck-typed, no base class needed):
//   isRemote        : boolean            — true for network-backed adapters
//   loadSync()      : stateObject | null — synchronous boot read; local only,
//                                          may throw on corrupt data (caller handles)
//   load()          : Promise<stateObject | null>
//   save(state)     : void | Promise<void>
//                     Local is synchronous and may throw QuotaExceededError so the
//                     existing quota-recovery path keeps working. Remote returns a
//                     Promise; the save orchestration is revisited when the async
//                     adapter lands (block D).
//   clear()         : void | Promise<void>

const INPACT_STATE_KEY = 'inpact-state';

class LocalStorageAdapter {
  constructor(key = INPACT_STATE_KEY) {
    this.key = key;
    this.isRemote = false;
  }

  // Synchronous read used by the constructor boot path. Returns the parsed
  // state object, or null if nothing is stored. Throws on corrupt JSON — the
  // caller (loadFromStorage) already catches and falls back to defaults.
  loadSync() {
    const saved = localStorage.getItem(this.key);
    if (!saved) return null;
    return JSON.parse(saved);
  }

  // Async form of loadSync, for a uniform interface with remote adapters.
  async load() {
    return this.loadSync();
  }

  // Synchronous on purpose: setItem throws QuotaExceededError synchronously,
  // and CycleBoardState.saveToStorage relies on catching that to run cleanup.
  save(state) {
    localStorage.setItem(this.key, JSON.stringify(state));
  }

  clear() {
    localStorage.removeItem(this.key);
  }
}

const APP_STATE_TABLE = 'app_state';

class SupabaseAdapter {
  // Takes an already-authenticated Supabase client and the signed-in user's
  // id. Auth itself (magic link, session handling) is AuthController's job
  // (block C) — this adapter only knows how to move state bytes once a
  // session exists. Row-level security (migrations/006_inpact_mvp.sql) is
  // the actual access boundary; this class does not re-check ownership.
  constructor(supabaseClient, userId) {
    if (!supabaseClient) throw new Error('SupabaseAdapter requires a Supabase client');
    if (!userId) throw new Error('SupabaseAdapter requires a userId');
    this.client = supabaseClient;
    this.userId = userId;
    this.isRemote = true;
  }

  // No synchronous remote read exists. CycleBoardState's constructor boot
  // path only ever uses LocalStorageAdapter; swapping in SupabaseAdapter
  // happens after sign-in via the async migration flow (block D), which
  // calls load()/save() directly rather than going through the constructor.
  loadSync() {
    throw new Error('SupabaseAdapter has no synchronous load — use load() (async)');
  }

  async load() {
    const { data, error } = await this.client
      .from(APP_STATE_TABLE)
      .select('state, updated_at')
      .eq('user_id', this.userId)
      .maybeSingle();
    if (error) throw error;
    if (!data) return null;
    // Surface the row's updated_at on the returned state so callers (the
    // block D migration step) can compare it against local's _localUpdatedAt
    // without a second round trip.
    return { ...data.state, _remoteUpdatedAt: data.updated_at };
  }

  async save(state) {
    const { _remoteUpdatedAt, ...persisted } = state;
    const { error } = await this.client
      .from(APP_STATE_TABLE)
      .upsert({ user_id: this.userId, state: persisted }, { onConflict: 'user_id' });
    if (error) throw error;
  }

  async clear() {
    const { error } = await this.client
      .from(APP_STATE_TABLE)
      .delete()
      .eq('user_id', this.userId);
    if (error) throw error;
  }
}

// Export for Node-based tests; harmless in the browser.
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { LocalStorageAdapter, SupabaseAdapter, INPACT_STATE_KEY, APP_STATE_TABLE };
}
