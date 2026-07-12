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

// Export for Node-based tests; harmless in the browser.
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { LocalStorageAdapter, INPACT_STATE_KEY };
}
