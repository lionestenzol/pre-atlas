/**
 * SQLite driver selection shim — libSQL spine-adoption spike (Turso ecosystem, step 1).
 *
 * Default driver is better-sqlite3 → ZERO behavior change for existing callers.
 * With DELTA_DB_DRIVER=libsql, route through Turso's `libsql` npm package, which is
 * a better-sqlite3-compatible SYNCHRONOUS fork (identical new Database / prepare /
 * pragma / transaction / exec / close surface). This is the reversible proof step:
 * flip the flag, run delta-kernel's own test suite, and confirm the drop-in against
 * real workloads BEFORE any commitment in the deterministic hub.
 *
 * Why libSQL and not the Turso-Rust engine: libSQL is the same org's PRODUCTION
 * SQLite fork and ships native vector search + embedded-replica sync (what Lattice/
 * Ledger actually need) without betting the deterministic core on a beta rewrite.
 * The Turso-Rust headline feature (BEGIN CONCURRENT / MVCC concurrent writes) is
 * contraindicated here — delta-kernel serializes writes on purpose to keep the delta
 * hash-chain fork-free (see sqlite-storage.ts header). Parked as a lead, not the spine.
 */

import BetterSqlite3 from 'better-sqlite3';

/** The better-sqlite3 instance type; libSQL matches this surface at runtime. */
export type SqliteDatabase = BetterSqlite3.Database;

/**
 * Construct the SQLite handle for the configured driver.
 * @param dbPath absolute path to the database file
 */
export function makeDatabase(dbPath: string): SqliteDatabase {
  if (process.env.DELTA_DB_DRIVER === 'libsql') {
    let libsql: { default?: typeof BetterSqlite3 } & typeof BetterSqlite3;
    try {
      // Lazy require: libsql is only needed when the flag is on, so the default
      // path never depends on it being installed.
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      libsql = require('libsql');
    } catch {
      throw new Error(
        "DELTA_DB_DRIVER=libsql but the 'libsql' package is not installed. Run: npm i -D libsql",
      );
    }
    const Ctor = (libsql.default ?? libsql) as typeof BetterSqlite3;
    return new Ctor(dbPath);
  }

  return new BetterSqlite3(dbPath);
}
