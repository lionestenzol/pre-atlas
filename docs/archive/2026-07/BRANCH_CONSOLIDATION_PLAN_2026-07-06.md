# Branch Consolidation Plan — feat/atlas-setup-ui
> Generated 2026-07-06, read-only against git history. Supersedes the open questions in
> memory `project_branch_layer_audit` (2026-06-28). Companion to `GIT_SESSION_INVENTORY_2026-06-28.md`
> (the old worklist index — **index only, never evidence**; drift verified, see §5).

**Branch state, verified today:**
- `feat/atlas-setup-ui` = **204 ahead of local `main`** (tip `118861d`, 2026-05-05), **0 behind**.
- vs `origin/main` (tip `679aeb5`, PR#21 merge, 2026-06-13): **195 ahead, 0 behind** — still a clean fast-forward against BOTH.
- Local `main` is **9 behind `origin/main`**. Last fetch: 2026-06-26 (`.git/FETCH_HEAD`) — refetch before trusting any ahead/behind number.
- 38 commits landed since the 2026-06-28 inventory (`fb8e7d6` → `667d756`), enumerated in §3.

---

## 1. The four decisions (resolved)

### Q1 — Unit of audit: **LAYER, verdicted at HEAD. Commits are evidence, not units.**
204 per-commit verdicts is the wrong shape at both ends of the distribution:
- **Big layers:** droplist's 41 commits were already audited *as a product* (market-ready audit ~95% at `f6c97d0`, spec in `DROPLIST_MARKET_READY_SPEC.md`). Re-verdicting each commit re-derives what one surface-level verdict already answers. Inside a layer, later commits routinely supersede earlier ones (e.g. `55e05ca` closes bugs opened by earlier droplist commits) — a per-commit pass would issue verdicts on states that no longer exist.
- **Tail layers:** 21 layers have exactly 1 commit, so there layer = commit and the distinction is free.
- **Exception:** a layer gets sub-split ONLY when its commits form distinct arcs with different fates (droplist has 3 arcs: packet-engine era 2026-06-07→06-17, lifecycle-bricks era 06-20→06-25, ship era 06-25→06-26). Split by arc, still not by commit.

### Q2 — Ordering: **recency-banded, not size-banded.** Band 1 = the live July campaign, Band 2 = the tail, Band 3 = the big old layers.
- Neither proposed order survives the data. *Biggest-first* starts with droplist, whose real blocker is a PR-collision **decision** (§2 flag 1), not audit labor — you'd stall on item 1. *Smallest-first* clears the tail but lets the July work go cold.
- **Verdict cost grows with staleness.** The 38 new commits (07-04→today) are verdictable in minutes each while context is hot — several are provably live ("phone buzzed on both smoke-test runs", `b47ea1f`). In two weeks they cost as much as the May archaeology.
- Momentum psychology is served anyway: Band 1 + Band 2 together close ~36 of 45 layers fast; Band 3 is 9 layers, each already pre-documented (droplist audit doc, seam's 160+20 tests, delta-scp's PR-review trail).

### Q3 — Output format: **this document IS the ledger (markdown, in-repo). No new festival. Spawned build-work flows into the existing FA0001.**
- The audit is a read+verdict pass. fest's proof-gate (`recon_verify`) gates *done* on code-recon receipts citing changed code — a verdict usually produces **no diff**, so the gate has nothing to bite on. Proof-gating a judgment is circular.
- The heavier machinery already exists where it earns it: **`finish-atlas-fleet-FA0001`** (`festival-project/festivals/planning/finish-atlas-fleet-FA0001/`) is already driving the July campaign (commits `6e8992e`, `4e12bfe`, `7fe013f`, `84e947a` all cite "FA0001 task 02"). Every UNFINISHED verdict that needs real build work becomes an FA0001 task (proof-gated there, where it belongs). Creating a second festival for the audit would double-wrap the same work.
- Enforcement without machinery: **a verdict row with no citation is invalid** (§4). The ledger lives in git; its diffs are reviewable; that satisfies the every-message-DoD rule.

### Q4 — Per-layer DoD: verdict ∈ **{FINISHED · UNFINISHED · DEAD · INERT}**, issued at HEAD, ≥1 tool-provable citation.
Spot-checks (§5) show the proposed 3-state taxonomy is almost right but needs two refinements:
- **INERT** (new): docs/banking/merge commits (`db2ce94`, `fb8e7d6`, the 14-commit `(none)` layer) need no verdict work — they land with the merge, done. Without this state they'd waste ~20 audit slots.
- **DEAD carries a reason + disposition:** `DEAD(abandoned)` or `DEAD(superseded by <hash>)`, and disposition = capsule-tag or move to `services/_retired/` + `RETIRED.md` (the pattern `6e8992e`/`84e947a` already established). **Never delete** — per the capsule doctrine in `CAPSULES.md` and code-as-furniture.

---

## 2. Risk flags — independent of the audit, act on these first

1. **[HIGH — decision needed] Three overlapping DropList PRs are open against `main`: #23, #24, #25.** Verified: PR#25's branch (`ship/droplist-2026-06-25`) has 2 commits not on this branch and its `services/droplist` tree is **1,622 lines behind** this branch's (`git diff --stat feat/atlas-setup-ui origin/ship/droplist-2026-06-25 -- services/droplist`). Merging any of them on GitHub (a) moves `origin/main`, instantly ending the clean-fast-forward invariant against a 204-commit branch, and (b) lands a *stale* droplist over the branch's newer one at the next sync. **Action: declare `feat/atlas-setup-ui` the canonical droplist line; close #23/#24/#25 with a comment pointing here (or retarget them at this branch). Also triage #22 (snake game) and stale #19/#20.** This is a 15-minute decision, not audit labor.
2. **[MED] Remote sessions fork from a broken `main`.** Load-bearing fixes exist only on this branch: `4334139` (ESM `require()` crash in signals-store), `3b486b6` (buildCockpit crash), `10643bd` (uasc execution daemon never ran → jobs never completed), `ddad44a` (aegis-fabric approve didn't execute), `7124d61` (control-panel/timeline UIs couldn't auth). Any Claude-web/Codex session starting from `origin/main` inherits all of these and may burn time re-fixing them (the `claude/*` and `codex/*` remote branches prove such sessions happen). Mitigated by flag-1's PR cleanup + making this branch the default working ref; fully cured only by the eventual merge.
3. **[MED] Local `main` is 9 behind `origin/main`, fetch is 10 days old.** Every "204 ahead / 0 behind" claim is only as good as the last fetch. `git fetch origin` at the start of any consolidation session; fast-forwarding local `main` to `origin/main` is lossless whenever convenient.
4. **[LOW, standing] The unbanked working tree remains the real loss-risk** (per `project_branch_layer_audit`): untracked `1010/`, `services/cognitive-sensor/loop_clearer.py`, `loopclearer-working.jpeg`; `services/crucix` submodule dirty. Git can't protect what it doesn't hold.
5. **[LOW] Same-day doc drift:** `CLAUDE.md` still says Optogon signal emission is off, but `09d64fb` (today) sets `OPTOGON_SIGNAL_EMIT=1` in `.claude/launch.json` + `services/optogon/start.bat`. Fix the sentence when verdicting the `atlas` layer.

---

## 3. Updated taxonomy — 45 layers / 204 commits

### 3a. The 38 post-inventory commits (2026-06-28 → 2026-07-06), by layer
These are in NO inventory until now. `+` = new layer.

**delta-kernel (+12 → 14 total)** — the close-the-loop campaign core:
`7880517` test pending-action confirmation gate · `42487e6` forward approval_required→Optogon · `4334139` fix ESM require crash · `3b486b6` fix buildCockpit crash · `4b82016` auto-tier completions→closure feedback · `450d8f0` overlap guard on prepared-work pending actions · `f6a0c61` wire prepared-work→pending_action (notify/confirm) · `0633505` fix 30s pending timeout · `de4dd81` task completion→ntfy.sh push · `348788b` mode gate at confirm/claim time · `8bddfa4` fix stale imports in deferred Delta-State Fabric · `7124d61` UIs authenticate to /api/*

**uasc-executor (+4 → 5)**: `b47ea1f` SEND_DRAFT real ntfy push (live-verified) · `14dbcf6` DEPLOY builds delta-scp-web for real · `84987e2` gate real-effect profiles behind aegis-fabric · `10643bd` fix execution daemon never running

**openclaw (+3, new layer)**: `c1d8981` /pending lists pending actions · `4e12bfe` /approve→delta-kernel confirmation gate (FA0001-02) · `7fe013f` repoint openclaw+memory-hub off retired services (also touches memory-hub)

**fleet-retire (+2, new layer)**: `6e8992e` retire mosaic-dashboard, strip mirofish from search-stack · `84e947a` retire mosaic-orchestrator + mirofish (both → `services/_retired/` + RETIRED.md)

**inpact (+2 → 4)**: `ffbb050` pending-action confirm banner · `47c11dd` seeded priorities complete real tasks
**atlas (+2 → 3)**: `221a888` agent front-door doctrine + daemon-seeded day plan · `09d64fb` schedule cognitive-sensor daily pipeline + enable Optogon signals
**one each:** atlas-map-api `ef62908` (per-capability call counter) · lattice `c6567cd` (memory-hub search box) · aegis-fabric `ddad44a` (approve actually executes) · audit `c357aa7` (manifest builder script) · cognitive-sensor `e7b3926` (idea-registry regen) · fest `aa0c0d0` (FS0001 planning files) · +cycleboard `667d756` (docs refresh) · +anatomy-ext `f5b8504` (sitepull daemon auto-launch)
**(none)/docs-banking (+5 → 14)**: `fb8e7d6` ATM synthesis + inventory bank · `db2ce94` durable session artifacts · `6f58d68` TRUST_BOUNDARY.md · `64e650c` /prune note · `e29281a` gitignore + skills-lock

### 3b. Full layer table (old counts from `GIT_SESSION_INVENTORY_2026-06-28.md` Part A/B + §3a)

| Layer | commits | Band | Layer | commits | Band |
|---|--:|:-:|---|--:|:-:|
| droplist | 41 | 3 | fest-reconcile | 2 | 2 |
| delta-kernel | 14 | **1**/2¹ | tools | 2 | 2 |
| (none) docs/merges | 14 | 2 | fleet-retire + | 2 | 1 |
| lattice | 13 | 3 | fest | 2 | 1/2 |
| seam | 12 | 3 | atlas+cognitive-sensor | 1 | 2 |
| cognitive-sensor | 12 | 3 | atlas-audit · atlas-cli | 1 ea | 2 |
| atlas-map-api | 9 | 3 | atlas_explorer · autopsy | 1 ea | 2 |
| atlas-map | 8 | 3 | autostart · cortex | 1 ea | 2 |
| delta-scp | 8 | 3 | delta-kernel,uasc | 1 | 2 |
| audit | 8 | 3 | delta-scp-web · gateway | 1 ea | 2 |
| map | 6 | 3 | launch · memory-hub | 1 ea | 2 |
| uasc-executor | 5 | **1** | optogon · pre-atlas | 1 ea | 2 |
| inpact | 4 | **1** | search · services | 1 ea | 2 |
| search-stack | 4 | 2 | setup · skills | 1 ea | 2 |
| hydra | 3 | 2 | triangulation | 1 | 2 |
| wall | 3 | 2 | cycleboard + | 1 | 1 |
| atlas | 3 | **1** | anatomy-ext + | 1 | 1 |
| openclaw + | 3 | **1** | | | |
| aegis-fabric | 3 | **1**/2¹ | **Total: 45 layers** | **204** | |
| canvas-engine | 2 | 2 | | | |

¹ split layers: new commits Band 1, the 2 old commits (2026-05/06) Band 2.
`+` = layer new since the inventory. Old-commit enumeration: inventory Part B (index only).

---

## 4. Verdict protocol (the per-layer DoD)

Every layer row in §6 is CLOSED when it has, written into this file:

```
VERDICT: FINISHED | UNFINISHED | DEAD(abandoned|superseded by <hash>) | INERT
EVIDENCE: <file:line at HEAD, or command + output, or runtime probe (atlas_call/curl), dated>
NEXT:     (UNFINISHED only) ONE concrete action + where (file:line) — becomes an FA0001 task if build-sized
DISPOSAL: (DEAD only) capsule tag name, or services/_retired/ move
```

Rules:
- **Evidence at HEAD only.** The 06-28 inventory and memory files are pointers, never citations — both have verified drift (§5).
- A runtime claim ("live", "wired", "running") needs a runtime probe, not a code read (`atlas_call`, `curl`, or the service's own test suite run fresh).
- No verdict without evidence; no NEXT without a file:line; batch-verdicting a band in one pass is fine, hand-waving a layer is not.
- UNFINISHED items too small for fest (< ~30 min) may be fixed inline during the audit session (code-as-furniture) and re-verdicted FINISHED with the fix cited.

---

## 5. Inventory drift — why HEAD-only evidence is mandatory (verified samples)

1. `b47ea1f` (07-04) closed the SEND_DRAFT-ntfy item that memory `project_atlas_physical_leaves` still lists as the "smallest win" TODO — commit message documents live phone verification.
2. `6e8992e` (07-06) rewired the `search-stack` layer (mirofish stripped) — that layer's 4 inventoried commits no longer describe its HEAD state.
3. mosaic-dashboard / mosaic-orchestrator / mirofish now live under `services/_retired/` — any old-layer verdict touching them must use the new paths.
4. `CLAUDE.md` vs `09d64fb` Optogon-enable contradiction (§2 flag 5).

---

## 6. Execution ledger

Work top to bottom. Start-of-session ritual: `git fetch origin` → confirm `git rev-list --count feat/atlas-setup-ui..origin/main` still 0 → open this file.

### Band 0 — decisions, before any audit labor (~30 min)
- [ ] **PR triage:** close or retarget #23/#24/#25 (droplist), decide #22/#20/#19. Canonical line = this branch. VERDICT/EVIDENCE: PR states after action, `gh pr list`.
- [ ] **Bank the working tree:** commit or explicitly discard `1010/`, `loop_clearer.py`, `loopclearer-working.jpeg`; resolve crucix dirty state (never `git add -A` across it).

### Band 1 — the July campaign, while it's hot (~1 session, 27 commits, 8 layer-rows)
- [ ] **delta-kernel(new-12)** — probe: does the full pending-action loop run? `npm test` on the confirmation-gate test (`7880517`), then live: governance daemon tick → `GET /api/actions/pending` → confirm → execution. Known-good starting points: `services/delta-kernel/src/governance/governance_daemon.ts:826`, `src/api/server.ts:2564-2719`, `src/core/cockpit.ts:499`.
- [ ] **uasc-executor(new-4)** — SEND_DRAFT/DEPLOY live-verified per commit messages; re-prove with one profile run; check `10643bd` daemon is actually scheduled now.
- [ ] **openclaw(3)** — `/pending` and `/approve` against a live delta-kernel; tests in `services/openclaw/tests/test_skills.py`.
- [ ] **inpact(new-2)** — confirm banner renders + completes against Phase-2 producer (:3006).
- [ ] **atlas(new-2)** — is the scheduled cognitive-sensor pipeline registered (Task Scheduler / launch.json)? Is Optogon emitting with `OPTOGON_SIGNAL_EMIT=1`? Fix the stale CLAUDE.md sentence here (§2 flag 5).
- [ ] **aegis-fabric(new-1) `ddad44a`** — REQUIRE_HUMAN approve→execute path, one live round-trip.
- [ ] **fleet-retire(2) + atlas-map-api `ef62908` + lattice `c6567cd` + audit `c357aa7` + cognitive-sensor `e7b3926` + fest `aa0c0d0` + cycleboard + anatomy-ext** — expected mostly FINISHED/INERT; one citation each.
- [ ] **(none) docs-banking(5 new + 9 old)** — expected INERT wholesale; confirm nothing in `db2ce94`'s landed docs contradicts HEAD badly enough to mislead.

### Band 2 — tail triage (~1-2 sessions, ~40 commits, ~28 layer-rows)
One verdict each; most are one-file features from May/June. Pre-known signals:
- [ ] hydra(3) · wall(3) — files live (`apps/hydra/hydra.html`, `apps/lattice/wall.html` verified at HEAD); expected FINISHED-as-museum or DEAD(capsule); decide, don't polish.
- [ ] search-stack(4) — verdict at HEAD *post*-`6e8992e` (mirofish gone).
- [ ] aegis-fabric(old-2) · canvas-engine(2) · delta-kernel(old-2) · fest-reconcile(2) · inpact(old-2) · tools(2) — quick.
- [ ] The 21 one-commit layers — expected: many FINISHED (they shipped and stuck: gateway timeout `27cac49`, launch port fix `fd3af58`, optogon close-fix `9f922f5`), a few DEAD(superseded) (`autopsy`, `setup`, `atlas_explorer` — check against today's `services/_retired/` reality and the Setup-UI state), docs INERT.

### Band 3 — the big nine, one real session each (~3-5 sessions, ~113 commits, arcs where noted)
- [ ] **droplist(41, 3 arcs)** — gated on Band 0 PR decision. Arc verdicts: packet-engine era (superseded by later arcs?), lifecycle-bricks (67 tests per memory), ship era (market-ready audit ~95%, `DROPLIST_MARKET_READY_SPEC.md` + 3H/7M/6L open items → those become the NEXT actions).
- [ ] **seam(12)** — memory claims LIVE with 160+20 tests; re-run them at HEAD, one `seam` CLI round-trip.
- [ ] **delta-scp(8)** — externally PR-reviewed (CodeRabbit) + shipped on :3012; expected FINISHED cheap.
- [ ] **lattice(13)** — known NEXT already on file (viewmodel+write-back, memory `project_atlas_lattice_seam`); verdict likely UNFINISHED with that as the action.
- [ ] **cognitive-sensor(12)** — includes the May refactors + Rung-4 bridge; NB untracked `loop_clearer.py` belongs to this surface (Band 0).
- [ ] **atlas-map(8) · map(6) · atlas-map-api(old-8)** — the GPS/gateway arc; gateway is load-bearing (CLAUDE.md front door) → FINISHED must be proven by `atlas_describe_list` + one `atlas_call` live.
- [ ] **audit(8)** — mostly docs of past audits; expected INERT/FINISHED.

### Exit gate — when the branch merges
All 45 layer-rows verdicted with evidence · every UNFINISHED either fixed inline or an FA0001 task exists · every DEAD disposed (capsule/_retired) · PRs resolved (Band 0) · then `git fetch && git checkout main && git merge --ff-only feat/atlas-setup-ui` is pure housekeeping, exactly as `project_close_it_out_strong` framed it.

---
*Provenance: all counts/hashes from `git log main..feat/atlas-setup-ui` and `git rev-list` at 2026-07-06; diffs spot-checked: `a11b00a`, `2ae0365`, `f6a0c61`, `b47ea1f`, `09d64fb`, `6e8992e`, `4e12bfe`, `7fe013f`, `84e947a`, `64e650c`, `e29281a`, `db2ce94`, `6f58d68`. PR overlap measured against `origin/ship/droplist-2026-06-25` and `origin/droplist-lifecycle-spine`. No git state was modified.*
