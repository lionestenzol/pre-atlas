# Trial B · Hunt-first · v2

## Sanity check
- branch: claude/main-triage-26f4a5
- HEAD: 5b96bf0f422abda1ff32fd50f0d1c62f03876312
- services/droplist exists: yes

## Hunt phase
- Search angles used:
  1. `Signal\.v1|signal_v1|SignalV1|SIGNAL_V1` — structural name variants
  2. `emit_signal|publish|send_signal|emit\(` — emission verbs
  3. `consume_signal|receive|dag_to_signal|consume` — consumption verbs
  4. `n8n_webhook|DROPLIST_N8N_URL|DROPLIST_ATLAS_SIGNALS_URL|DROPLIST_DIRECT_SIGNALS_URL` — env/transport names
  5. `source_layer|optogon|droplist.*source` — schema field identifiers
  6. `trimmed to|label.*140|label.*80|80 char|140 char` — drift-specific angle (label truncation)
- Total hits: ~55 across 11 files

## Local map phase
- delta-scp invoked? no (binary not present in repo; no `services/delta-scp` directory found)
- Localized skeleton (hit files within services/droplist):

```
services/droplist/
├── droplist/
│   ├── atlas_signal.py       ← EMIT: dag_to_signal(), emit_signal()
│   └── graph_engine.py       ← EMIT: _maybe_emit_atlas_signal() called at settle
├── test_atlas_emit.py        ← test fixture: mock HTTP server acts as downstream sink
├── test_atlas_signal.py      ← test fixture: structural + strict schema validation
├── PACKETS/
│   ├── 005_atlas_seam_contract.md   ← contract spec (some stale fields — see drift)
│   └── 006_live_atlas_signal_emission.md  ← live wire spec
└── BIBLE.md                  ← §16 Atlas Seam (authoritative mapping docs; one stale diagram line)
```

## Emit sites
| file | line | snippet | confidence |
|---|---|---|---|
| `droplist/atlas_signal.py` | 87 | `def dag_to_signal(dag: dict, source_layer: str = "optogon") -> dict[str, Any]:` | high |
| `droplist/atlas_signal.py` | 143–151 | assembles and returns the full Signal.v1 dict with `schema_version`, `id`, `emitted_at`, `source_layer`, `signal_type`, `priority`, `payload` | high |
| `droplist/atlas_signal.py` | 154 | `def emit_signal(signal: dict, url: str, timeout: float = 10.0) -> dict[str, Any]:` | high |
| `droplist/atlas_signal.py` | 161–176 | `urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")` — zero-dep HTTP POST | high |
| `droplist/graph_engine.py` | 21 | `def _maybe_emit_atlas_signal(dag: dict) -> None:` — wrapper called after every settle | high |
| `droplist/graph_engine.py` | 28 | `url = os.environ.get("DROPLIST_ATLAS_SIGNALS_URL")` — env-gate: no url → silent return | high |
| `droplist/graph_engine.py` | 40 | `sig = atlas_signal.dag_to_signal(dag)` — mapping call | high |
| `droplist/graph_engine.py` | 42 | `resp = atlas_signal.emit_signal(sig, url)` — POST call | high |
| `droplist/graph_engine.py` | 203 | `_maybe_emit_atlas_signal(dag)` — callsite inside `run_graph()`, after `_finalize(dag)` | high |

## Consume sites
| file | line | snippet | confidence |
|---|---|---|---|
| `test_atlas_emit.py` | 47–62 | `class _CaptureHandler(BaseHTTPRequestHandler)` — stdlib HTTP server that captures POSTs for test assertion; not a production consumer | medium (test-only) |
| `test_atlas_emit.py` | 53–57 | `self.received.append({"path": self.path, "content_type": ..., "body_raw": body})` — captures Signal.v1 body for structural assertion | medium (test-only) |

**Note:** There is no production Signal.v1 consumer inside `services/droplist`. The service is a pure producer. The real consumer is `POST /api/signals/ingest` in `services/delta-kernel` (out of scope per hard rules). The test capture handler above is the only receive-path code in this boundary.

## Drift findings

### 1. Env var name: `DROPLIST_DIRECT_SIGNALS_URL` (spec) vs `DROPLIST_ATLAS_SIGNALS_URL` (code)
PKT-005 and the BIBLE §16 flow diagram describe the direct-POST bypass env var as `DROPLIST_DIRECT_SIGNALS_URL`. PKT-006 shipped it as `DROPLIST_ATLAS_SIGNALS_URL`.

Evidence:
- `PACKETS/005_atlas_seam_contract.md:87` → `DROPLIST_DIRECT_SIGNALS_URL set`
- `BIBLE.md:316` → `.emit_signal()    DROPLIST_DIRECT_SIGNALS_URL set)`  ← stale diagram label
- `droplist/graph_engine.py:28` → `os.environ.get("DROPLIST_ATLAS_SIGNALS_URL")` ← actual code
- `test_atlas_emit.py:85` → `os.environ["DROPLIST_ATLAS_SIGNALS_URL"] = url` ← test uses code name
- `PACKETS/006_live_atlas_signal_emission.md:26` → `DROPLIST_ATLAS_SIGNALS_URL` ← PKT-006 renamed it

**Impact:** The BIBLE §16 bypass diagram and PKT-005 doc are stale. Anyone reading PKT-005 or the BIBLE §16 diagram and trying to wire the direct bypass would set the wrong env var. Code and PKT-006 are consistent with each other.

### 2. `payload.label` truncation: 80 chars (PKT-005 spec) vs 140 chars (code + BIBLE §16)
PKT-005 specifies the label should be trimmed to 80 characters. The implementation and the updated BIBLE §16 use 140.

Evidence:
- `PACKETS/005_atlas_seam_contract.md:66` → `dag.goal` **(trimmed to 80 chars)**
- `BIBLE.md:294` → `dag.goal` **(trimmed to 140 chars)**
- `droplist/atlas_signal.py:103` → `label = (dag.get("goal") or "").strip()[:140]` ← code uses 140
- `droplist/atlas_signal.py:76` → `(n.get("title") or "Awaiting human")[:140]` ← action_options label also 140

**Impact:** PKT-005 spec is stale. The change from 80→140 is consistent between implementation and BIBLE §16, so it is intentional. PKT-005 was not updated when the limit was widened. Low impact in practice.

### 3. `source_layer = "optogon"` placeholder (known, tracked as OQ-17)
DropList emits `source_layer: "optogon"` because the Signal.v1 schema enum does not include `"droplist"`. This is documented as a known placeholder, tracked in OQ-17.

Evidence:
- `droplist/atlas_signal.py:92–93` → code comment: `source_layer defaults to "optogon" because the Signal.v1 enum does not yet include "droplist". See OQ-17`
- `BIBLE.md:241` → OQ-17 entry: pending, touching `contracts/schemas/Signal.v1.json` (settled core)
- `test_atlas_signal.py:27` → `VALID_SOURCE_LAYERS = {"site_pull", "optogon", "atlas", "ghost_executor", "claude_code"}` ← no "droplist"

**Impact:** DropList cannot self-identify accurately in emitted signals. Atlas consumers cannot distinguish DropList emissions from optogon emissions. Deferred deliberately.

## Claims with evidence: 3
## Claims without evidence: 0

## Self assessment
- What was easy: The Signal.v1 emit path is tightly concentrated in two files (`atlas_signal.py`, `graph_engine.py`) with clear naming. Hunt phase converged fast.
- What was hard: Distinguishing production consume from test-harness receive (the `_CaptureHandler` is a mock, not a real consumer). No actual consume-side code exists in this boundary.
- What might be missed: Any indirect Signal.v1 construction outside `atlas_signal.py` (e.g. hand-crafted dicts POSTed elsewhere). Checked via multiple patterns; nothing found. The n8n flow JSON (`n8n_flows/droplist_to_atlas_signal.json`) is mentioned but not committed — so a potential Signal.v1 producer in the n8n flow is invisible from this repo.
- Confidence: high (emit path); medium (consume — none found, which is the true answer, not a miss)

## Tool calls made (approximate): 14
## Wall-clock time: ~8 minutes
