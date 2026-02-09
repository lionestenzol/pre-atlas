# Delta Kernel

**Version:** 0.1.0
**Port:** 3001

Delta Kernel is the state synchronization and governance engine for Pre Atlas. It provides deterministic, delta-driven state management with autonomous behavioral enforcement.

---

## Quick Start

```bash
# Start the API server
npm run api

# Start the CLI interface
npm run start

# Run tests
npm run test
```

The API runs on `http://localhost:3001`.

---

## Architecture

```
delta-kernel/
├── src/
│   ├── api/
│   │   └── server.ts          # REST API (Express)
│   ├── cli/
│   │   ├── index.ts           # CLI entry point
│   │   ├── app.ts             # Application logic
│   │   ├── input.ts           # Keyboard handling
│   │   ├── renderer.ts        # Terminal rendering
│   │   └── storage.ts         # Data persistence
│   ├── core/
│   │   ├── types.ts           # Type definitions
│   │   ├── delta.ts           # Delta operations + Law Genesis Layer
│   │   ├── routing.ts         # Mode computation
│   │   ├── templates.ts       # Mode templates
│   │   ├── tasks.ts           # Task management
│   │   └── ...                # Additional modules
│   └── governance/
│       └── governance_daemon.ts # Autonomous mode daemon
├── specs/                      # 18 specification documents
├── web/                        # React web UI
└── package.json
```

---

## API Endpoints

### State Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Get current system state |
| `/api/state` | PUT | Update system state |
| `/api/state/unified` | GET | Merged Delta + Cognitive state |
| `/api/state/unified/stream` | GET (SSE) | Stream unified state + delta events |

**Realtime (SSE) event format**

The `/api/state/unified/stream` endpoint emits server-sent events with JSON payloads:

```
event: unified_state
data: {"ok":true,"ts":"2024-01-01T00:00:00.000Z","delta":{...},"cognitive":{...},"derived":{...},"errors":[]}

event: delta_created
data: {"ok":true,"ts":"2024-01-01T00:00:00.000Z","delta":{...}}
```

### Task Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tasks` | GET | List all tasks |
| `/api/tasks` | POST | Create new task |
| `/api/tasks/:id` | PUT | Update task |
| `/api/tasks/:id` | DELETE | Archive task |

### Law Endpoints (Phase 4-5B)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/law/close_loop` | POST | Canonical closure event |
| `/api/law/acknowledge` | POST | Acknowledge daily order |
| `/api/law/violation` | POST | Log build violation |
| `/api/law/override` | POST | Log enforcement override |

### Governance Daemon
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/daemon/status` | GET | Daemon state + job history |
| `/api/daemon/run` | POST | Manually trigger a job |

### Cognitive Bridge
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ingest/cognitive` | POST | Ingest from cognitive-sensor |

---

## Governance Daemon

The daemon runs scheduled jobs for autonomous mode governance:

| Job | Schedule | Description |
|-----|----------|-------------|
| `heartbeat` | Every 5 min | Health check |
| `refresh` | Every hour | Run cognitive refresh |
| `day_start` | 06:00 | Reset daily counters, mode recalc |
| `day_end` | 22:00 | Streak reset, mode recalc |
| `mode_recalc` | Every 15 min | Autonomous mode governance |

---

## Mode Rules (Phase 5B)

| Closure Ratio | Mode | build_allowed |
|---------------|------|---------------|
| >= 0.80 | SCALE | true |
| >= 0.60 | BUILD | true |
| >= 0.40 | MAINTENANCE | false |
| < 0.40 | CLOSURE | false |

---

## Data Storage

State is persisted to `.delta-fabric/` at the repo root:

- `entities.json` - Entity state
- `deltas.json` - Delta audit log

Set `DELTA_DATA_DIR` environment variable to customize location.

---

## Specifications

See `specs/` directory for detailed module specifications:

- `v0-schemas.md` - Schema definitions
- `v0-routing.md` - Mode routing logic
- `v0-task-lifecycle.md` - Task state machine
- `phase-5b-closure-mechanics.md` - Closure mechanics (Phase 5B)
- `module-1` through `module-11` - Feature modules

---

## Dependencies

- **express** - REST API framework
- **node-cron** - Scheduled job execution
- **tsx** - TypeScript execution
- **cors** - Cross-origin support

---

## Related Documentation

- [PHASE_ROADMAP.md](../../PHASE_ROADMAP.md) - Implementation history
- [CONTEXT_PACKET.md](../../CONTEXT_PACKET.md) - System context
- [FILE_MAP.md](../../FILE_MAP.md) - File connections

---

*Part of the Pre Atlas personal operating system.*
