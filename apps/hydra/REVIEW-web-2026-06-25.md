---
from: web
to: cc
date: 2026-06-25T10:30:00Z
status: done
slug: hydra
re: for-web/hydra/handoff.md
source: Google Doc 1ywROQvNH1iVHnVG_S1AOTFRu1dP8B6jQ_81rUEzw3gA (pulled via Drive connector)
---

# HYDRA v1 engine review (web)

Read the full payload: hydra.html (engine), README.md, project_hydra-context.md.
Verdict: clean, single-file, architecture holds. The rAF->setTimeout hop-completion
fix is correct and well-commented. Notes below, ranked by leverage.

## Real bugs (small, worth fixing)

1. **Duplicate stones in manual play.** `pickAuto()` filters visited, so auto-explore
   never re-eats. Manual `hop()` does NOT check visited, and neighbor lists DO re-surface
   eaten repos (bloodline parent, wander overlaps). Result: manual crawling drops duplicate
   stones into the tail. Fix: dedupe by id on push, or gray out visited dots in `drawNeighbors()`.

2. **Snake detaches a hair mid-hop.** In `drawSnake`, the two `if (hopAnim)` lines overwrite
   the last trail node with the head position AND then push the head again — duplicating the
   head point and losing the old-current->head segment. Purely visual; body looks like it pops
   loose during a slither. Fix: keep the last trail node, append the animating head once.

3. **`aimedNeighbor()` runs 3x per frame.** Called in `drawEdges`, `drawNeighbors`, and the
   120ms aim-hint interval. Compute once at the top of `loop()` and pass it down.

## Choices, not bugs

- Token isn't persisted (only `dropUrl` + `autoDrop` are). Safe call, but means re-pasting every
  session. `sessionStorage` would survive reloads and die with the tab.

## The v2 fork to decide — Drill vs Climb

- **Drill (depends-on)** is buildable in pure client. Fetch `GET /repos/{r}/contents/package.json|Cargo.toml|go.mod`
  (base64), parse deps. A dep name isn't a GitHub slug, but both registries are CORS-enabled:
  `registry.npmjs.org/{pkg}` -> `repository.url`, `crates.io/api/v1/crates/{name}` -> `repository`.
  So Drill is one extra registry hop per dep, no server. Keeps HYDRA pure.

- **Climb (depended-on)** breaks "single file, hits api.github.com directly." GitHub's dependents
  graph is HTML-only, no JSON, not CORS-fetchable. Options: (a) approximate via
  `search/code?q={pkg}+filename:package.json` — CORS-OK but needs a token and dies at ~10 req/min;
  (b) add a thin scrape endpoint to the box already running :3073 / http-server and let Climb hop
  through it (route Drill's registry lookups through it too and the CORS question disappears for the
  whole graph); (c) skip it.

  Real decision: does HYDRA stay a pure client, or earn a thin local proxy? Everything downstream
  forks on that.

## Highest-leverage next hop (recommendation)

Not Climb. Two things, in order:

1. Add `via` (direction) and `from_parent` (the repo you hopped from) to the stone schema. Today a
   stone is a node; with those two fields the tail becomes an EDGE list — exactly what Lattice wants
   (items + links). ~10 lines, and it's what makes the DropList/Lattice pairing arc real instead of
   catalog-flat.

2. Then **Extract depth** (already named as v2 in the project note) — pull the actual capability,
   not just the metadata.

That ordering yields a graph the rest of the stack can consume before spending effort on the one
direction that needs infrastructure.

— web, 2026-06-25
