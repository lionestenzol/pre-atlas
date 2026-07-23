# HYDRA 🐍

**A snake that crawls GitHub hop by hop.** Each repo is a dot. You aim the head at the next
dot, it hops, it eats a *stone* (one capability), and the stone joins the tail. The tail is
your gauntlet — a treasury of intelligence you can wield (and, later, pair with DropList).

Single self-contained file: [`hydra.html`](hydra.html). No build, no server required for play —
it hits `api.github.com` directly (CORS-enabled). Double-click to open, or serve it:

```
# from repo root
npx http-server apps/hydra -p 8898 -c-1 --cors
# → http://127.0.0.1:8898/hydra.html
```

> Unauthenticated GitHub calls get **60 req/hr** — plenty for manual hop-play. Paste a
> personal-access token in the top-left field to lift it to **5000/hr**. The token stays in
> your browser; it is never sent anywhere but GitHub.

---

## The loop (one hop = one turn)

1. **Drop** the head on a seed repo (`owner/repo`).
2. HYDRA surfaces the reachable dots (neighbors) under the active **Direction**, each with a
   one-line read + signal strength (stars → 1–5 pips).
3. **Aim** — move the mouse toward a dot; the nearest one to your aim locks (blue edge).
4. **Hop** — click or press **Space**. The head slithers to the dot and **eats the stone**.
5. The eaten repo's neighbors become the new field. Repeat. The snake's body is the trail of
   repos you've crawled; the tail data is your stone treasury.

## Directions (edge rules — switch any time to *turn* the snake)

| Direction | Edge rule | GitHub call | Status |
|---|---|---|---|
| **Tour a mind** | same owner | `GET /orgs|users/{owner}/repos` | ✅ live |
| **Wander** | shared top topic | `GET /search/repositories?q=topic:{t}` | ✅ live |
| **Bloodline** | forks + parent/source | `GET /repos/{r}/forks` + `.parent` | ✅ live |
| **Tour me** | your own account | `GET /users/lionestenzol/repos` | ✅ live |
| **Drill** | depends on (manifest) | parse `Cargo.toml`/`package.json` | 🔜 v2 |
| **Climb** | depended on by | dependents (no JSON API — needs scrape) | 🔜 v2 |

Switching direction mid-run re-surfaces the current repo's neighbors under the new rule —
that's the snake genuinely turning (start on Wander to find a region, switch to a focused
rule once you're somewhere interesting).

## Auto-explore (the snake pilots itself)

Hit **▶ Auto-explore** and HYDRA crawls on its own: each tick it picks the highest-signal
**unvisited** neighbor and hops. When it has exhausted a region (everything reachable is
already visited), it **rotates direction** (Tour → Wander → Bloodline) to escape the clique
and find fresh ground; if nothing fresh remains anywhere, it stops.

- **Rate-aware pacing:** ~6s/hop unauthenticated, ~2.6s/hop with a token. Auto-explore
  **pauses itself** when GitHub credits run low (≤2 left).
- Hop completion is driven by a real timer, **not** `requestAnimationFrame`, so auto-explore
  keeps progressing even when the tab is backgrounded (rAF is throttled there; the snake would
  otherwise hang mid-hop).
- Tick **auto→DropList** to have every auto-eaten stone fed to DropList hands-free.

## Eating for real — digest through delta-scp (the throughput)

A stone is no longer just a note. When you eat a repo (and **🧬 digest** is on), HYDRA sends it
to the **HYDRA engine** (`apps/hydra/engine.py`, :8899), which calls **delta-scp** (:3012) to
clone + symbol-extract the repo. A real structural map lands on the stone and the full digest
is cached to `apps/hydra/vault/`:

```
🧬 digested · 461 files · 2808 symbols · graph 2821/979
  merge-deep.d.ts · 59 sym · Writable, ArrayTail, SimplifyDeepExcludeArray…
```

That's the difference between read-only and Pac-Man: **bytes move.** GitHub repo → cloned →
digested → a map of its actual types/functions on your disk.

**To run the eating chain (3 services):**
```
# 1. delta-scp demo gateway (Supabase-free, synchronous digest engine)
preview_start delta-scp-demo          # or: cd ~/pre-atlas/services/delta-scp && npx tsx src/demo-server.ts
# 2. HYDRA engine (holds delta-scp's key, serves the browser with CORS)
preview_start hydra-engine            # or: python apps/hydra/engine.py
# 3. the game
preview_start hydra                   # http://127.0.0.1:8898/hydra.html
```

The engine reads delta-scp's Bearer key from its `.env` server-side — **the key never touches
the browser.** delta-scp clones via `git`, so big repos are slow; eat small/medium repos first.
If the engine or delta-scp is down, the stone shows a `⚠ engine offline` note and nothing else
breaks.

## DropList pairing

Every stone can flow into **DropList** (`services/droplist`, `POST /api/drop`) as a drop —
this is the "tail pairs with DropList" arc, at catalog depth.

- **⇪ on a stone** sends that one; **→ DropList** (treasury footer) sends every un-sent stone.
- The drop URL is editable (default `http://127.0.0.1:3073/api/drop`) and persisted.
- DropList's bouncer returns **`secured`** (kept as a packet) or **`dropped`** (filtered as
  noise/dup); HYDRA shows that verdict as a badge on each stone.
- The raw drop text is `HYDRA stone · {repo} [{type}, signal n/5] — {what} · pairs with: … · {url}`.

> Requires the DropList service running on :3073 (`preview_start droplist`, or
> `uvicorn droplist.server:app --port 3073`). If it's down, the stone badge shows `offline`
> and nothing is lost — resend later.

## Stones (catalog depth — v1)

Each hop records one stone, derived deterministically from repo metadata:

```json
{
  "id": "tursodatabase-turso",
  "from_repo": "tursodatabase/turso",
  "type": "technique|component|doctrine|tool|lead",
  "name": "turso",
  "what": "<repo description>",
  "pairs_with": "<you fill this in — what in your stack it slots into>",
  "signal": 5,
  "language": "Rust", "stars": 22069, "url": "https://github.com/...",
  "caught_at": "2026-06-24"
}
```

- **Type** is heuristic-guessed and **click-to-cycle** in the treasury.
- **pairs_with** is yours to write — the bridge from "interesting repo" to "thing I can use."
- **Export JSON** dumps the whole tail in this schema. Stones + trail persist in `localStorage`
  (`hydra_v1`) so a refresh resumes your crawl.

## Done-condition (v1 — shipped & verified 2026-06-24)

> HYDRA sits on one seed repo, pulls its real neighbors **live from the GitHub API**, shows them
> with one-line reads, you pick one, it **hops** and **records the first stone** to the tail.

Verified end-to-end in-browser: `tursodatabase/turso → turso-client-php → libsql-client-ts`,
2 hops, 2 stones, snake advanced, state persisted, zero console errors.

## Growth path (after the snake can move)

- ✅ **Auto-explore** — the snake pilots its own hops (shipped 2026-06-24).
- ✅ **DropList pairing (catalog depth)** — stones → drops, with secured/dropped verdicts
  (shipped 2026-06-24).
- **v2 Extract depth** — pull the actual snippet/code into a vault DropList can draw from
  (catalog → extract).
- **v2 edge rules** — Drill (manifest parse) + Climb (dependents scrape).
- **v2 Lattice** — feed stones into Lattice as item types (export schema already matches).
- **v3 Integrate** — wire an eaten capability into the stack live.
