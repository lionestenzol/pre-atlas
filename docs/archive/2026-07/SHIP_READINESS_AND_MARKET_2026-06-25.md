# Pre Atlas — Ship-Readiness & Market Reality (2026-06-25)

Method: `/groundwork` → 36-agent verified workflow. Every surface audited first-hand
(file:line), headline readiness claims adversarially re-checked, 10 categories
researched against the real market. **Verified %** = the number after the skeptic pass
(auditors inflate; the refute pass corrected 5 of them).

---

## 1. The brutal truth (read this first)

1. **Nothing is "click-and-play" as a product.** Of 17 surfaces, exactly 2 open-and-run
   with no terminal — `hydra` (a game) and `webos-333` (a self-declared stub). Everything
   else is "partial" (needs `npm`/`uvicorn` + a backend/API key) or "no" (CLI/infra).
   A stranger cannot drag-drop or double-click any of these and use them today.

2. **The most *finished* things are in the most *crowded* markets; the things with a real
   *wedge* are the least finished.** crucix/delta-scp-web/search-stack are the most polished
   but the market says "me-too, don't ship." The only two products the market says are
   *worth shipping* — `anatomy-saas` and `droplist` — sit at 30% and 45%.

3. **Several have real security holes that block any exposure beyond localhost** — one is a
   straight RCE. None are ADA-compliant. See §4.

---

## 2. Ship-readiness table (verified)

Sorted by verified readiness. `→` = number changed by the skeptic pass.

| # | Surface | Verified % | Product? | Click&Play | Sec | A11y | Sani | #1 blocker to ship |
|---|---------|-----------:|----------|-----------|-----|------|------|--------------------|
| 1 | **crucix** (OSINT dashboard) | 66 | yes | partial | 🔴poor | 🔴poor | 🔴poor | XSS via innerHTML of OSINT/LLM text; no auth; CORS * |
| 2 | **delta-scp-web** (SaaS UI) | 55→**65** | yes | partial | 🟢good | 🟡fair | 🟢good | Backend lives in a *different* repo; uncommitted; no tests |
| 3 | **search-stack** | **60** | infra | no | 🟡fair | n/a | 🟢good | No UI; API keys in plaintext .env; no auth (localhost-only) |
| 4 | **inpact** | **58** | yes | partial | 🟢good | 🟢good | 🟢good | No auth, no backend persistence (localStorage only), no Stripe |
| 5 | **anatomy-extension** | 62→**58** | yes | partial | 🟡fair | 🔴poor | 🟡fair | Not packaged (.crx/store); empty icons; dead "edit" button |
| 6 | **atlas-map-api** | 72→**55** | infra | partial | 🟢good | 🟡fair | 🟡fair | Internal tool, repo-specific; 2 servers by hand |
| 7 | **delta-kernel** (engine+CycleBoard) | **52** | yes | partial | 🟡fair | 🟡fair | 🟡fair | React UI broken under auth; API test suite 0/9; Dockerfile runs TUI not API |
| 8 | **blueprint-generator** | 70→**50** | yes | partial | 🟢good | 🟡fair | 🟢good | **SUPERSEDED by canvas-engine** (self-marked); 0 tests |
| 9 | **lattice** | **45** | yes | partial | 🟡fair | 🟡fair | 🟡fair | Empty shell unless delta-kernel up; hardcoded loopback; 0 tests |
| 10 | **droplist** | **45** | yes | **no** | 🟡fair | 🔴poor | 🟡fair | **No UI at all** (JSON API only); no packaging; uncommitted |
| 11 | **canvas-engine** (screenshot→code) | **35** | infra | no | 🟢good | n/a | 🟢good | No UI in this path; needs `claude` CLI / ANTHROPIC key |
| 12 | **anatomy-saas** | **30** | not yet | partial | 🟢good | 🟡fair | 🟢good | No product around the core; center mockup is a **stub**; private/v0.0.0 |
| 13 | **mosaic-dashboard** | **30** | yes | partial | 🔴poor | 🟡fair | 🟡fair | **RETIRED** (self-marked); secret leaked to client; needs 5-6 services |
| 14 | **code-converter** (C2NL) | **30** | yes | partial | 🔴poor | 🟡fair | 🟡fair | **Unauth, unsandboxed arbitrary code exec on 0.0.0.0 (RCE)** |
| 15 | **cognitive-sensor** | **28** | infra | partial | 🟡fair | 🔴poor | 🟡fair | Single-tenant, owner's data baked in; pipeline + 3 servers |
| 16 | **hydra** (game) | **62** | yes | **yes** | 🟡fair | 🔴poor | 🟡fair | XSS at hydra.html:678; engine CORS * + no-auth POST /eat; uncommitted |
| 17 | **webos-333** | 62→**20** | yes | **yes** | 🟡fair | 🔴poor | 🔴poor | Self-declared **stub** ("do not build on this"); XSS |

(hydra is listed last because high % + "yes" play, but it's a toy — see market.)

---

## 3. "Could a user click and play?" — no, almost nowhere

- **Open-a-file-and-it-works:** only `hydra` and `webos-333` (and webos is a stub).
- **Needs a dev toolchain** (`npm install` + dev server, or `uvicorn`, often + a second
  backend, often + an API key): delta-scp-web, inpact, lattice, delta-kernel, canvas-engine,
  anatomy-saas, mosaic-dashboard, code-converter, blueprint-generator, atlas-map-api.
- **Headless / no UI:** droplist (JSON API only), search-stack (API+MCP), cognitive-sensor.

There is **no packaged, installable, double-click artifact** in the portfolio. Closest to a
real front-door UX: **inpact** (single-page, good a11y, but localStorage-only, no accounts).

---

## 4. Security & ADA — the must-fix list

**Critical (block ANY network exposure):**
- 🔴 **code-converter** — unauthenticated, **unsandboxed arbitrary code execution** bound to
  `0.0.0.0`. This is remote code execution. Do not expose. Fix before touching again.
- 🔴 **mosaic-dashboard** — tenant secret leaked to the client + unauthenticated proxy to
  internal services. (Also already retired.)
- 🔴 **crucix** — stored/reflected **XSS** (untrusted OSINT/LLM text → innerHTML), no auth, CORS `*`.
- 🟠 **hydra** — XSS at `hydra.html:678` (GitHub repo name → innerHTML); engine `POST /eat`
  is CORS `*` + no auth (any web page can drive it).
- 🟠 **webos-333** — XSS in the in-browser "browser" app + file naming.

**localhost-only-safe but blocks hosting:** droplist, search-stack, cognitive-sensor,
atlas-map — all CORS `*` + no auth (fine bound to 127.0.0.1, hard blocker the moment you host).

**Sanitization is mostly OK** where it matters for SaaS: delta-scp-web, anatomy-saas,
inpact, search-stack, canvas-engine all grade **good** (JSX/manual escaping + boundary validation).

**ADA / a11y:** **none are compliant.** Best is **inpact** (good — semantic HTML, labels).
Everything else is fair/poor and needs an a11y pass: aria-live on status regions, labels on
color-only indicators, keyboard/focus, and a real contrast check. UIs heavy on canvas/graph
(hydra, lattice, cognitive-sensor) are the furthest from ADA.

---

## 5. Competitor ranking — us vs the market

| Surface | Market rank | Real wedge? | Biggest gap |
|---------|-------------|-------------|-------------|
| **anatomy-saas** | niche (unclaimed seam) | ✅ **Yes** — deterministic, shareable, commit-able visual SPEC of one component (no tool makes this exact artifact) | No live interactivity; single-component/framework; unproven; no product shell |
| **droplist** | niche / not-yet | ✅ **Yes** — "tool-verified done-condition" on a personal capture→execute loop; nobody mainstream verifies a task is *actually* done | No UI; no durability story vs Temporal; no integrations; not deployed |
| **delta-kernel / CycleBoard** | niche / not-yet (toy vs incumbents) | ⚠️ Maybe — "governance kernel for a human" (mode-cycling + enforced doctrine) | No users, no mobile, no calendar/email integrations, no gamification |
| **delta-scp** | behind | ❌ me-too of Repomix `--compress` | Adoption (~21k★ incumbents), relevance ranking (Aider PageRank), multi-format, secret-strip |
| **search-stack** | behind / niche | ⚠️ only the specialized intents (legal/SEC/gov/academic) | No relevance/merge/dedup layer; no cost accounting; no extraction |
| **atlas-map** | not-competitive | ❌ as general tool | No language-aware code-intel; single-repo; no refs/defs; vs free Sourcegraph/Zoekt |
| **canvas-engine** | not-competitive | ❌ commoditized | No design model, no deploy/preview loop, no full-app gen, no Figma; vs v0/Lovable/Bolt |
| **cognitive-sensor** | behind | ❌ it's literally BERTopic | No interactive topic-map UI; no auto-labeling; no scale; vs Nomic Atlas |
| **lattice** | not-competitive (prototype) | ❌ | Persistence (in-memory!), sync, mobile, collaboration; vs Obsidian/Tana/Notion |
| **hydra** | toy | ❌ | No dep/call edges, no clear JTBD, no LLM-context packaging; vs GitDiagram/snk |

**Market says "worth shipping": only `anatomy-saas` (sharp niche) and `droplist` (real
unoccupied wedge).** `delta-kernel` is a defensible-but-hard niche. Everything else: the
research verdict was explicitly *do not ship as a standalone product.*

---

## 6. The strategic read (built ≠ shippable ≠ worth shipping)

- **Most polished, weakest market:** delta-scp-web (65%, but Repomix already won the category).
- **Best wedge, least built:** anatomy-saas (30%) — the deterministic shareable component spec
  is genuinely unoccupied, but there is no product around the compiler yet and the centerpiece
  mockup is a stub.
- **Best risk-adjusted ship:** **droplist** — the hard part (engine: 67 tests, DAG, scheduler,
  tool-verified done) is *done*, the wedge is *real and unoccupied*, and its #1 gap is exactly
  the thing that's straightforward to build: **a UI front door.** It's also where the last
  several sessions of work already landed.

---

## 7. Recommended ship order

1. **droplist** → give it a UI + auth + always-on deploy. Closest real product with a real moat.
2. **anatomy-saas** → build the product shell (web app + real mockup render + packaging) around
   the proven compiler. Highest ceiling.
3. **inpact** → it's the most a11y-clean front-door UX; add a backend + accounts + Stripe and it's
   a sellable personal-execution app.
4. Park as internal infra (do **not** productize): search-stack, atlas-map, canvas-engine,
   cognitive-sensor, delta-kernel-as-consumer-app.
5. Fix-or-fence (security): code-converter (RCE), crucix/hydra/webos (XSS), mosaic (retired).
