# Pre Atlas — Architectural Decision Records

> Each decision follows the ADR format: Title, Status, Context, Decision, Consequences.
> Decisions are numbered sequentially. Status is one of: accepted, superseded, deprecated.
> For the architecture these decisions shape, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## ADR-001: Hub-and-spoke over SQLite + HTTP

**Status:** Accepted

**Context:** The system needed a way for 19+ services to share state. Common patterns include event buses (Kafka, NATS, RabbitMQ), shared databases (PostgreSQL with multiple clients), and service meshes. These patterns optimize for distributed teams and horizontal scaling, neither of which applies here -- this is a single-user, single-machine system.

**Decision:** All services communicate through one-way HTTP calls to a central hub (`delta-kernel`, port 3001). The hub persists state in SQLite (better-sqlite3). There is no event bus, no shared database between services, and no message queue. Services consume JSON validated by JSON Schema contracts at every seam.

**Consequences:**
- Simple to reason about: every state question has one answer (ask delta-kernel).
- No infrastructure dependencies beyond Node.js and Python.
- Trade-off: no pub/sub means services must poll or be triggered explicitly.
- Trade-off: single-writer hub serializes all state mutations, limiting concurrent write throughput. This is intentional -- hash-chain integrity requires serialization (see ADR-002).

---

## ADR-002: Append-only hash-chained deltas (RFC 6902 JSON Patch)

**Status:** Accepted

**Context:** The system needed a mutation model that supports full state reconstruction, auditability, and conflict detection. Traditional CRUD overwrites history. Event sourcing frameworks add infrastructure weight.

**Decision:** All state mutations are expressed as RFC 6902 JSON Patches, appended to `.delta-fabric/deltas.json`. Each delta includes a hash of the previous delta, forming a hash chain. Current materialized state lives in `.delta-fabric/entities.json` (24 entity types). Any entity's state can be reconstructed by replaying its deltas from the beginning.

**Consequences:**
- Full audit trail: every change is recorded with its predecessor hash.
- Conflict detection: a forked hash chain is immediately visible.
- Storage grows monotonically. No compaction is implemented.
- 10 documented hash-chain fork points exist from concurrent writes without file locking (see `HASH_CHAIN_FORKS.md`). File locking was deliberately omitted -- the single-writer hub design (ADR-001) is the intended serialization mechanism.

**Lineage:** This design is inherited from the ATM (Asynchronous Temporal Mesh) target architecture, where hash-chained deltas correspond to the ATM's "Sundial" timestamping mechanism. See ADR-010.

---

## ADR-003: Automation gated off by default

**Status:** Accepted

**Context:** Three services (`cortex`, `optogon`, `cognitive-sensor`) can act autonomously -- executing tasks, writing signals back to delta-kernel, or triaging conversation data. Autonomous action on a personal governance system carries real risk: a misconfigured executor could close loops the user hasn't actually completed, or start work the mode FSM hasn't authorized.

**Decision:** All autonomous write-back is gated behind environment flags that default to off:
- `cortex` requires `CORTEX_BRIDGE_APPLY=1`
- `optogon` requires `AUTO_TRIAGE_APPLY=1`
- `optogon` signal emission requires `OPTOGON_SIGNAL_EMIT=1`
- `cognitive-sensor` triage is unscheduled (hand-cranked via `at`)

Only `delta-kernel`'s governance daemon runs autonomously (heartbeat, mode recalc, daily resets).

**Consequences:**
- Safe by default: a fresh deployment does nothing autonomously beyond governance housekeeping.
- Each autonomous capability requires an explicit, deliberate opt-in.
- Trade-off: the system cannot self-heal or self-optimize until gates are opened. This is the intended posture -- the system governs a human, so premature automation is worse than no automation.

---

## ADR-004: 6-mode deterministic FSM (no AI judgment)

**Status:** Accepted

**Context:** The system's core question is "what should I be doing right now?" Many personal productivity tools answer this with AI recommendations, heuristics, or learned preferences. These approaches are opaque, non-reproducible, and hard to debug when they give wrong answers.

**Decision:** Mode is computed by a pure lookup table (LUT). Five signals (`sleep_hours`, `open_loops`, `assets_shipped`, `deep_work_blocks`, `money_delta`) are each bucketed into LOW/OK/HIGH. The bucket tuple indexes directly into a routing table that outputs one of 6 modes: RECOVER, CLOSURE, MAINTENANCE, BUILD, COMPOUND, SCALE. No weights, no ML model, no randomness.

**Consequences:**
- Fully deterministic: same inputs always produce same mode. Debuggable by inspection.
- The routing table is the entire governance policy, readable in one screen (`routing.ts`).
- Trade-off: no nuance. The LUT cannot express "usually BUILD but today feels off." This is intentional -- the system's value is that it overrides feelings with measurement.
- All `Record<Mode, ...>` types in the codebase must enumerate all 6 modes. The TypeScript compiler enforces completeness.

---

## ADR-005: File-based storage despite docker-compose existing

**Status:** Accepted

**Context:** `docker-compose.yml` defines PostgreSQL and Redis services. Database migrations exist in `db/`. However, the actual runtime has always used file-based storage: delta-kernel writes to `.delta-fabric/` (JSON files backed by SQLite), aegis-fabric writes to `.aegis-data/` (per-tenant JSON files).

**Decision:** Keep file-based storage as the runtime truth. The docker-compose and migration files are legacy artifacts from an earlier design phase, not active infrastructure.

**Consequences:**
- Zero infrastructure dependencies: no Docker, no PostgreSQL, no Redis required to run.
- Simple backup: copy the files.
- Trade-off: no concurrent multi-process access, no transactional guarantees beyond what SQLite provides. Acceptable for a single-user system.
- The docker-compose file should be treated as historical, not operational. Do not assume it reflects the running system.

---

## ADR-006: Windows-only scripts

**Status:** Accepted

**Context:** All automation scripts (`.ps1`, `.bat`) target PowerShell on Windows. No Unix equivalents exist. The system's single user runs Windows 11.

**Decision:** Accept Windows-only automation for now. Scripts use PowerShell syntax, Windows paths, and Windows-specific process management.

**Consequences:**
- The system cannot run its automation scripts on macOS or Linux without porting.
- This is an explicit portability gap, not an oversight. Porting is deferred until there is a real need (e.g., CI/CD on Linux, or a second user on macOS).
- Service code itself (TypeScript, Python) is cross-platform. Only the glue scripts are Windows-locked.

---

## ADR-007: Capability and trust closed by source

**Status:** Accepted

**Context:** Autonomous systems that can expand their own capabilities at runtime are vulnerable to injection attacks, review fatigue, and cascading trust failures. A staged-proposal-plus-review-gate protects determinism and auditability but not against injection, because the reviewer becomes the new target.

**Decision:** Capability and trust change only by source-diff + redeploy. Never by a runtime request, proposal, or payload -- no matter how many review steps sit in between. The action surface is architecturally unreachable from anything that processes untrusted content. Not defended against -- absent.

Verified surfaces:
- delta-kernel `ActionType`: 7 fixed strings in `types-core.ts:263-270`, enforced at execution.
- UASC executor: 10 tokens seeded once in `schema.sql:55-65`, no insert route.
- UASC lab reference: open (live `register_graph()` method) but not wired to anything running.

**Consequences:**
- No runtime path can register, approve, or unlock a new action, token, or capability.
- Adding a new capability requires a code change, a commit, and a redeploy.
- Trade-off: the system cannot learn new actions from experience. This is the point -- see [TRUST_BOUNDARY.md](TRUST_BOUNDARY.md).

---

## ADR-008: Mode thresholds intentionally differ between services

**Status:** Accepted

**Context:** cognitive-sensor and delta-kernel both compute mode from signals, but use different thresholds. cognitive-sensor triggers CLOSURE at `open_loops > 20`. delta-kernel triggers CLOSURE at `open_loops >= 4`. Initial reaction was to treat this as a bug.

**Decision:** The divergence is intentional. cognitive-sensor operates on raw conversation data (thousands of detected "loops," many of which are noise). delta-kernel operates on curated state (loops that survived triage). The threshold that's appropriate for raw data is not appropriate for curated data, and vice versa.

**Consequences:**
- Both services are "correct" for their contexts.
- Anyone reading the code must understand which context they're in before judging whether a threshold is wrong.
- If the two services are ever unified under a single pipeline, the thresholds must be reconciled.

---

## ADR-009: libSQL as delta-kernel database spine

**Status:** Accepted

**Context:** delta-kernel's SQLite access was originally hardcoded to `better-sqlite3`. The system needed a path toward the Turso cloud platform (for potential future sync/replication) without changing the existing driver contract or taking on the Turso Rust beta engine's MVCC semantics (which conflict with the serialized single-writer design per ADR-001 and ADR-002).

**Decision:** Introduce a driver shim at `services/delta-kernel/src/cli/db-driver.ts` (`makeDatabase`). Default remains `better-sqlite3`. Setting `DELTA_DB_DRIVER=libsql` routes through `@libsql/client` (tursodatabase's production better-sqlite3-compatible fork). Both drivers are proven green across all test suites (verified 2026-06-25/26).

**Consequences:**
- Zero risk to existing behavior: default driver unchanged.
- Future Turso cloud sync is possible without a driver rewrite.
- The default has NOT been flipped to libSQL. Flipping is a separate deliberate move.
- `BEGIN CONCURRENT` (MVCC) from the Turso Rust engine is explicitly contraindicated -- the hub serializes writes on purpose for hash-chain integrity.

---

## ADR-010: delta-kernel is the ATM scoped down

**Status:** Accepted

**Context:** Pre Atlas's delta-kernel was not designed from scratch. It descends from the ATM (Asynchronous Temporal Mesh) -- a planned distributed temporal coordination system for mesh networks. The full ATM required hardware (LoRa radios), multi-node coordination, and federated learning, none of which a solo developer could build alone.

**Decision:** Scope the ATM down to its software-only core and ship it as delta-kernel. Inherit the ATM's design constraints even where the current system doesn't strictly need them:
- `delta.ts` hash-chained deltas = the ATM "Sundial" timestamping mechanism
- `delta-sync.ts` `DEFAULT_MAX_PACKET_BYTES = 220` = LoRa-safe packet sizing
- No blobs, deterministic conflict resolution = ATM transport constraints
- File-based append-only storage = ATM offline-first requirement

**Consequences:**
- Design choices that look arbitrary in a single-machine app (tiny packet sizes, no blobs, hash chains) have a clear origin and purpose.
- The ATM's 21-part architecture is the latent roadmap. If hardware becomes available, delta-kernel is the seed engine.
- Trade-off: the system carries constraints inherited from a distributed target that may never be built. These constraints are load-bearing for auditability and conflict detection even in the single-machine case, so they earn their keep.
