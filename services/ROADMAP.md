# Atlas Fleet — Finish-It-All Roadmap

_Created 2026-07-05. Companion to [FLEET_INVENTORY.md](./FLEET_INVENTORY.md)._
_Scope chosen: **truly finish all 20 services** (~7-11 working days)._

> ⚠️ This competes with the canvas-engine 90-day commitment (deadline 2026-07-21).
> canvas-engine is already COMPLETE — this roadmap finishes the *rest* of the fleet.

**End-state (DONE):** every service either COMPLETE + correctly wired + verified, or
explicitly RETIRED with a successor pointer. Map current. Autostart = true live set.
One directive flows intake → governance → execution → approval → channel.

**Guardrail:** safeties stay ON. Do NOT flip delta-kernel autonomy `enabled:true`.
Human-in-loop approval gate is the stated stance.

---

## Phase 0 — Truth & Cleanup · ~0.5 day
- [ ] Kill zombie `mosaic-orchestrator:3005` (retired but running); remove from autostart
- [ ] Archive `mirofish/` + `mosaic-orchestrator/` → `services/_retired/` + `RETIRED.md` successor pointer (no deletion)
- [ ] openclaw `config.py` `orchestrator_url` → `cortex:3009`; strip dead `mirofish` refs (openclaw + memory-hub health-check)
- [ ] Regenerate `audit/system-index.json` — fix stale ports + the 3010 collision so index == live scan
- **DONE:** index matches reality; no retired service in autostart; `openclaw/skills/status` returns real data

## Phase 1 — Light Up the Spine · ~1 day
- [ ] Start NATS:4222 (cortex + ws-gateway need it). Skip Neo4j/Ollama (only retired mirofish used them)
- [ ] Boot cognitive-sensor:8765 FIRST (the hub), then droplist:3073, memory-hub:3071, search-stack:3070, atlas-map-api:3072, delta-scp:3012, crucix:3117
- [ ] Add search-stack provider keys (or accept free-tier)
- [ ] Verify: health + one real call each; openclaw `brief`/`fest` return live data
- **DONE:** full health scan all-green-or-idle; real daily brief pulls through openclaw

## Phase 2 — Finish the Partials · ~2-3 days
- [ ] ws-gateway:3011 — add tests; prove NATS→Socket.IO end-to-end (publish → browser sees it)
- [ ] uasc-executor:3008 — flesh daemon: poll delta-kernel for approved work, execute profile via command tokens, ack back; real tests
- [ ] triangulation:3074 — build Phase B (visual) + Phase C (API); consensus on a sample; B/C tested
- **DONE:** all three COMPLETE + tested

## Phase 3 — Finish perception (stub) · ~3-5 days ⚠️ long pole
- [ ] FIRST (architect): resolve perception vs triangulation overlap — subsume or feed? Decide before step 2
- [ ] TDD the 11 remaining pipeline steps (80% coverage)
- **DONE:** URL → canonical Element graph, deterministic, tested

## Phase 4 — Integration & Seal · ~1 day
- [ ] End-to-end: one directive → droplist → delta-kernel/aegis → cortex/optogon/uasc → mosaic-dashboard → openclaw notify
- [ ] Wire one real channel (`TELEGRAM_TOKEN`) so a notification leaves the box
- [ ] Regenerate map; set final autostart = true live set; flip FLEET_INVENTORY.md to all-green
- **DONE:** one-directive demo runs clean

---

**Critical path:** 0 → 1 gates everything. Phase 3 is the long pole + has the architectural fork.
**Per-phase ritual:** end each phase with a fleet health scan + FLEET_INVENTORY.md update.
