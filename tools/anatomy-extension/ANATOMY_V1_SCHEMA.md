# Anatomy v1 — Canonical Schema

**Status:** v1.0 · locked 2026-04-22
**Producers:** `anatomy-extension` (v0.2+), `web-audit/lib/anatomy.js`
**Consumers:** anatomy renderer (HTML), sitepull, inPACT anatomy-map skill, future LLM edit loop
**Source:** `_research/AUDIT_FINDINGS.md` § Repo 6 "Convergence options (A11)"

Schema convergence is the v0.2 architectural deliverable. Both the extension and `web-audit/lib/anatomy.js` previously emitted conceptually-identical output with divergent shapes. v1 is the superset.

---

## 1. Top-level envelope

```json
{
  "version": "anatomy-v1",
  "metadata": { ... },
  "regions": [ ... ],
  "chains":  [ ... ],
  "layers":  { ... }
}
```

| Field      | Type   | Required | Notes                                                            |
| ---------- | ------ | -------- | ---------------------------------------------------------------- |
| `version`  | string | yes      | Literal `"anatomy-v1"`. Bump on breaking changes.                |
| `metadata` | object | yes      | Provenance. See §2.                                              |
| `regions`  | array  | yes      | Visual / DOM regions. May be empty.                              |
| `chains`   | array  | yes      | Backend / data chains. May be empty.                             |
| `layers`   | object | yes      | Layer taxonomy with colors. Promoted from CSS to data model.     |

---

## 2. `metadata`

```json
{
  "target":    "https://example.com/",
  "mode":      "spa | mpa | extension",
  "source":    "index.html",
  "timestamp": "2026-04-22T19:10:00Z",
  "tools":     ["anatomy-extension@0.2.0"]
}
```

| Field       | Type     | Required | Notes                                                                 |
| ----------- | -------- | -------- | --------------------------------------------------------------------- |
| `target`    | string   | yes      | URL (web-audit) or page scope (extension).                            |
| `mode`      | string   | yes      | One of `spa`, `mpa`, `extension`.                                     |
| `source`    | string   | no       | Relative path to source file when known (web-audit).                  |
| `timestamp` | string   | yes      | ISO-8601 UTC.                                                         |
| `tools`     | string[] | yes      | Producer identifiers with version. At least one entry.                |

---

## 3. `regions[]`

Each region is a visual / DOM area worth labeling.

```json
{
  "id":        "header-nav",
  "n":         1,
  "name":      "Header",
  "layer":     "ui",
  "selector":  "header > nav",
  "file":      "index.html",
  "line":      12,
  "detection": "landmark",
  "desc":      "<header> landmark",
  "note":      "user free-text",
  "kind":      "sem",
  "bounds":    { "x": 0, "y": 0, "w": 1440, "h": 64 },
  "fetches":   [{ "method": "GET", "url": "/api/me", "ts": 1761166212345 }]
}
```

| Field       | Type    | Required | Notes                                                                                  |
| ----------- | ------- | -------- | -------------------------------------------------------------------------------------- |
| `id`        | string  | yes      | Stable slug. Unique within `regions[]`.                                                |
| `n`         | integer | yes      | Display number. 1-based. Shared namespace with `chains[].nodes[].n`.                   |
| `name`      | string  | yes      | Human label.                                                                           |
| `layer`     | string  | yes      | One of `ui`, `api`, `ext`, `lib`, `state`. See §5.                                     |
| `selector`  | string  | no       | CSS selector (extension). Present when DOM-resolvable.                                 |
| `file`      | string  | no       | Source file relative to output root (web-audit).                                       |
| `line`      | integer | no       | 1-based line number in `file`.                                                         |
| `detection` | string  | no       | How region was found. **Closed vocabulary in v0.4** · see §3.2.                        |
| `desc`      | string  | no       | Short machine description.                                                             |
| `note`      | string  | no       | User free-text (extension only). Stores dwell-duration when detection=`cursor-dwell`. |
| `kind`      | string  | no       | Extension classification. **Closed vocabulary in v0.4** · see §3.2.                    |
| `bounds`    | object  | no       | Viewport rect in CSS pixels `{x,y,w,h}` (extension, at capture time).                  |
| `fetches`   | array   | no       | Network calls attributed to this region. See §3.1.                                     |

### 3.2 Closed vocabulary (v0.4)

Both producers (`anatomy-extension` and `web-audit/lib/anatomy.js`) emit only values from the lists below. Consumers (canvas-engine pattern-library) are guaranteed to recognize every value. Values outside this set are dropped at envelope-build time by the extension and warned to the console.

Two-way contract: when canvas-engine adds a new detection, mirror it in `tools/anatomy-extension/lib/detection-vocab.js`. When the extension adds one, mirror it in `services/canvas-engine/src/pattern-library/normalize.ts`.

**`detection` values** (group routing in canvas-engine):

| Detection                          | Routes to    | Producer path                                  |
| ---------------------------------- | ------------ | ---------------------------------------------- |
| `r2-large-iframe`                  | clickable    | extension v2 cascade                           |
| `r3-label-with-control`            | clickable    | extension v2 cascade                           |
| `r4-span-with-control`             | clickable    | extension v2 cascade                           |
| `r5-search-indicator`              | clickable    | extension v2 cascade                           |
| `r7-native-interactive`            | clickable    | extension v2 cascade                           |
| `r8-event-handler-attrs`           | clickable    | extension v2 cascade                           |
| `r9-aria-role`                     | clickable    | extension v2 cascade                           |
| `r11-icon-sized-interactive`       | clickable    | extension v2 cascade                           |
| `r12-cursor-pointer`               | clickable    | extension v2 cascade                           |
| `auto-label`                       | clickable    | extension popup auto-label                     |
| `alt-click`                        | clickable    | extension manual alt+click                     |
| `manual`                           | clickable    | extension import-fallback                      |
| `legacy`                           | clickable    | extension v1 cascade                           |
| `custom-element`                   | clickable    | extension v2 cascade · custom HTML elements    |
| `cursor-dwell`                     | clickable    | extension watch · cursor-dwell observation     |
| `card-heuristic`                   | card         | extension v2 cascade                           |
| `pattern-repeat`                   | list         | extension v2 cascade · repeat-container        |
| `sem-h1` … `sem-h6`                | heading      | extension v2 cascade · semantic tags           |
| `sem-header`                       | landmark     | extension v2 cascade                           |
| `sem-footer`                       | landmark     | extension v2 cascade                           |
| `sem-nav`                          | landmark     | extension v2 cascade                           |
| `sem-main`                         | landmark     | extension v2 cascade                           |
| `sem-aside`                        | landmark     | extension v2 cascade                           |
| `sem-section`                      | landmark     | extension v2 cascade                           |
| `sem-form`                         | form         | extension v2 cascade                           |
| `form`                             | form         | web-audit/lib/anatomy.js                       |
| `landmark`                         | landmark     | web-audit/lib/anatomy.js                       |
| `heading`                          | heading      | web-audit/lib/anatomy.js                       |
| `button-cluster`                   | clickable    | web-audit/lib/anatomy.js                       |
| `hero`                             | clickable    | web-audit/lib/anatomy.js                       |

**`kind` values**: `sem` · `click` · `card` · `list` · `custom` · `watch`. The extension back-fills missing kinds from detection on validation (e.g. `pattern-repeat` → `list`, `card-heuristic` → `card`).

### 3.1 `fetches[]`

```json
{ "method": "GET", "url": "/api/me", "status": 200, "contentType": "application/json", "ts": 1761166212345 }
```

| Field         | Type    | Required | Notes                              |
| ------------- | ------- | -------- | ---------------------------------- |
| `method`      | string  | yes      | HTTP verb, uppercase.              |
| `url`         | string  | yes      | Absolute or root-relative.         |
| `status`      | integer | no       | HTTP status when observed.         |
| `contentType` | string  | no       | Response MIME.                     |
| `ts`          | integer | no       | `Date.now()` at observation.       |

---

## 4. `chains[]`

Backend / data chains. Each chain is an ordered sequence of nodes across layers.

```json
{
  "id": "chain-get-api-me",
  "nodes": [
    { "n": 6, "layer": "api", "label": "GET /api/me", "detail": "200 · json",
      "probe": { "method": "GET", "status": 200, "contentType": "application/json" },
      "file": "index.html", "line": 1 },
    { "n": 7, "layer": "ext", "label": "api.example.com", "detail": "inferred from probe" }
  ]
}
```

| Field         | Type    | Required | Notes                                                             |
| ------------- | ------- | -------- | ----------------------------------------------------------------- |
| `id`          | string  | yes      | Stable slug. Unique within `chains[]`.                            |
| `nodes[]`     | array   | yes      | 1+ nodes in display order.                                        |
| `nodes[].n`           | integer | yes | Display number. Continues namespace from last region.                |
| `nodes[].layer`       | string  | yes | See §5.                                                              |
| `nodes[].label`       | string  | yes | Headline (e.g. `GET /api/x`).                                        |
| `nodes[].detail`      | string  | no  | Secondary line (status, content-type, hostname).                     |
| `nodes[].probe`       | object  | no  | Raw probe record when chain came from observed traffic.              |
| `nodes[].file` `line` | —       | no  | Source link when node corresponds to a known file.                   |

---

## 5. `layers` taxonomy

Promoted from CSS to data so every consumer uses the same palette.

```json
{
  "ui":    { "color": "#c084fc" },
  "api":   { "color": "#f59e0b" },
  "ext":   { "color": "#818cf8" },
  "lib":   { "color": "#22c55e" },
  "state": { "color": "#a855f7" }
}
```

| Key     | Meaning                               | Default color |
| ------- | ------------------------------------- | ------------- |
| `ui`    | Visible DOM region                    | `#c084fc`     |
| `api`   | Backend endpoint                      | `#f59e0b`     |
| `ext`   | External / third-party service        | `#818cf8`     |
| `lib`   | Internal library or module            | `#22c55e`     |
| `state` | Persistent state (DB, cache, storage) | `#a855f7`     |

Consumers MAY add keys. Producers MUST NOT redefine the five above.

---

## 6. Numbering rule

Regions are numbered 1..R. Chain nodes continue at R+1, R+2, … across all chains. This gives every callout in the rendered HTML a unique `n` for interactive linking. (Invariant inherited from `web-audit/lib/anatomy.js:213-237`.)

---

## 7. Producer notes

### Extension (v0.2)
- Writes `regions[]` only; `chains[]` empty for now (populated once `page-world.js` network observer lands).
- `note` comes from user's per-label text (stored in `scopeLabels()` entry).
- `fetches` populated by `page-world.js` attribution pass.
- `kind` = existing `gatherCandidates()` classification — kept as-is.
- `layer` defaults to `ui`. Rules in §8 promote to `api`/`state` when signals present.
- Existing on-disk label shape (`{label, selector, ts, auto, kind}`) remains valid. Additive fields — readers tolerate missing keys.

### web-audit (`lib/anatomy.js`)
- Already emits a compatible subset. v1 migration is a rename pass:
  - `regions[i].n/name/file/line/desc` — unchanged.
  - Add `id` = existing `slug`, `layer: "ui"`, `detection` from emit-site.
  - `chains[i].nodes[j]` — add `id`, keep `{n, layer, label, detail}` (currently `{n, layer, hd, pth}`). Rename `hd→label`, `pth→detail`.
- Sidecar `anatomy.json` gains `version` and `layers` fields.

---

## 8. Layer-promotion rules (extension)

When emitting a region, default `layer: "ui"`. Promote if:

| Signal                                                       | Promote to |
| ------------------------------------------------------------ | ---------- |
| Element is `<form>` with a submit handler touching fetch/XHR | `api`      |
| Selector matches `[data-state]`, `[aria-live]`               | `state`    |
| Element has `data-anatomy-layer="…"` override                | override   |

(Extension v0.2 ships with the override rule only. Heuristics land with v0.2.1.)

---

## 9. Versioning

- `version: "anatomy-v1"` is frozen.
- Additive fields inside existing objects are non-breaking and can land at any time.
- Renames, removed fields, or changed layer keys require `anatomy-v2`.

---

## 10. Minimal valid example

```json
{
  "version": "anatomy-v1",
  "metadata": {
    "target": "https://example.com/",
    "mode": "extension",
    "timestamp": "2026-04-22T19:10:00Z",
    "tools": ["anatomy-extension@0.2.0"]
  },
  "regions": [
    { "id": "header", "n": 1, "name": "Header", "layer": "ui", "selector": "header", "kind": "sem" }
  ],
  "chains": [],
  "layers": {
    "ui":    { "color": "#c084fc" },
    "api":   { "color": "#f59e0b" },
    "ext":   { "color": "#818cf8" },
    "lib":   { "color": "#22c55e" },
    "state": { "color": "#a855f7" }
  }
}
```
