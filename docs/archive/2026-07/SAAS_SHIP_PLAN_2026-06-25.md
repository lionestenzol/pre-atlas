# Claude-Tools → SaaS — Ship Plan & Triage
**Date:** 2026-06-25
**Source:** `/groundwork` run on "which of my Claude Code tools should become their own SaaS with UIs, how and why"
**Scope:** The ~40 custom **Claude Code tools** (skills, slash commands, MCP servers, agents) at `~/.claude/skills/` — NOT the Pre Atlas backend services.

---

## The question (plain English)

Out of all the custom tools built for Claude Code, which ones could stand on their own as a **product people pay to use** (a website with a UI) — instead of just helper commands for one person?

## The filter that decides it

> **The SaaS test:** Can the tool stand *outside* the Claude Code harness, and is the valuable IP in *the tool* — or is the "product" just Claude wearing a costume? If the moat is a prompt, there is no moat: the customer can buy Claude directly.

That one test sorts everything into three tiers.

---

## TIER 1 — Real standalone SaaS (ship material)

### 1. `anatomy-map` → **Living architecture diagrams** ⭐ lead product
- **What it is today:** generates an interactive HTML artifact — UI mockup in the center, `file:line` callouts in the margins, a backend-chain strip (API → lib → external), click-to-code drawers with embedded source.
- **Why it's a SaaS:** it's the one tool that is *inherently visual* — exactly what every CLI dev tool lacks. Onboarding, legacy-code archaeology, and PR review all beg for "show me how this feature connects." Proven category: **CodeSee** (acquired), Swimm, Mintlify.
- **The UI / product:** connect a GitHub repo → pick a route/component → get a living anatomy diagram that **regenerates on every PR** and embeds in docs.
- **Moat:** `file:line` precision + backend-chain tracing beats hand-drawn diagrams *and* stays in sync. Recon proved **~70% is a deterministic compiler**, not a Claude wrapper.
- **Status:** ✅ **Build plan ready and validated** — see festival below.

### 2. `code-recon` + `verified-audit` + `claim-verifier` → **Trust layer for AI coding agents** ⭐ strongest moat
- **What it is today:** forensic, `file:line`-cited verification; verified-audit forces every finding to survive 2+ angle citations; claim-verifier adversarially tries to *refute* claims before they're reported.
- **Why it's a SaaS:** *the* 2026 problem — AI agents confidently lie about code ("X is read by Y," "no consumers," "dead code"). Bruke's own history has a busted claim (mosaic-orch "0 consumers" was false). Universal pain now across Cursor/Copilot/Claude Code users.
- **The UI / product:** paste (or pipe) an agent's report → get a **verdict table: verified / partial / busted**, each with proof. A lie-detector for your coding agent.
- **Moat:** the verification *protocol* is methodology IP, not a prompt. Most defensible thing in the toolset.
- **Status:** ⚠️ identified, **needs its own groundwork plan** before shipping. Pure prompt today (227/119-line SKILL.md, no backing code — the agent runtime is the backend).

### 3. `delta-scp` → **Repo → context skeleton API**
- **What:** repo URL → token-cheap symbolic map (tree + top-level symbols), plus a state-aware prune + Supabase AST graph-memory layer.
- **Why:** hot category (repomix, gitingest). Differentiator is the **graph-memory layer**, not the compression.
- **UI:** paste a repo → symbolic map + "context budget" slider + copy button. Dev tool, API-first.
- **Moat:** thin unless the graph layer is the headline. Most crowded of the four.
- **Status:** ✅ already a standalone service (`C:\Users\bruke\pre-atlas\services\delta-scp`, port 3012). Needs UI + hosting, not a rebuild.

### 4. `search-stack` → **Unified search API (an OpenRouter for search)**
- **What:** one router over 28 providers across 14 intent kinds; it picks the right provider per query.
- **Why:** developers hate gluing 10 search APIs together. "One endpoint, every surface" is a real dev-infra product.
- **UI:** API + playground + usage/budget dashboard (the `search_stack_budget` endpoint already exists).
- **Moat:** the intent→provider routing table.
- **Status:** ✅ already a standalone service (`services/search-stack`, port 3070). Needs UI + hosting + auth.

---

## TIER 2 — Productizable but crowded, or better as a feature

- **`fest`** — proof-gated project management ("'done' must be *proven*, not claimed"). Novel angle, but competes with Linear/Asana. **Fold into the Tier-1 code-intelligence product as the "plan" stage.**
- **`competitor-monitor`** — already SaaS-shaped, but the market (Crayon, Klue, Kompyte) is commoditized and undifferentiated.
- **`jargonize`** — translate a casual prompt into expert technical register. A fun, viral **consumer micro-SaaS / browser extension**. Cheap to ship, low moat, high shareability. The only Tier-2 worth shipping standalone — as a weekend toy, not a company.
- **`repo-inventory` / `atlas-map`** — "source of truth for a monorepo." Fold into the code-intelligence suite.

---

## TIER 3 — NOT SaaS today (the "needs creativity" parking lot)

These fail the SaaS test **as-is** — the IP belongs to the underlying library or to Claude, not to the wrapper. **This is the afternoon list:** the job is to find the creative angle that gives each one a real moat, or confirm it stays a personal tool.

| Tool | Why it fails the test today | Creative angle to explore this afternoon |
|------|------------------------------|------------------------------------------|
| `three-js`, `react-three-fiber`, `anime-js`(+migrate), `three-js-migrate` | Product is the OSS lib; wrapper is knowledge-on-tap | A *migration-as-a-service* (auto-upgrade three.js r150+ breakages) might be a real product — the migrate skills already encode the breakage knowledge |
| `remotion` | Wraps Remotion | Templated video-gen vertical (e.g. auto-changelog videos) could be a product |
| `mandelbulb3d`, `mandelbulber2` | Hobbyist fractal rendering | Niche; likely stays personal unless paired with a gallery/marketplace |
| `scrapling-official`, `web-audit`, `web-extract-workflow` | Wrap scraping libs | "Clone & understand any web app" has legal gray area but real demand — needs a careful wedge |
| `st3gg` | Steganography toolkit | Niche security/privacy product; small market |
| `wasp-patterns`, `coding-standards`, `backend-patterns`, `frontend-patterns`, `security-review` | Knowledge packs | Could become a "linter/standards-as-a-service," but commoditized |
| `weapon`, `project-finisher`, `autopilot`, `mini-ship`, `groundwork`, `claude-bridge`, `handoff-out`, `continuous-learning-v2`, `eval-harness`, `verification-loop`, `codex-delegate`, `strategic-compact`, `cookbook` | These are *the workflow itself* — CC-harness orchestration | They *build* the Tier-1 products; a creative angle would be packaging the whole workflow as a hosted "AI dev studio," but that's a platform play, not a single SaaS |

---

## The one real insight

There isn't one SaaS in the toolset — there's **one coherent product made of four tools**, and `groundwork` already chains it:

> **delta-scp (ingest) → code-recon / verified-audit (verify = the moat) → anatomy-map (visualize = the front door) → fest (plan with proof)**
> = *"Understand, trust, and plan changes to any codebase — with every AI claim verified against ground truth."*

`anatomy-map` is the screen you demo. `code-recon`/`verified-audit` is why it's defensible. Lead marketing with the **anatomy diagram + the verdict table** — the two screens a stranger instantly understands.

---

## The build plan that's ready NOW

**Festival:** `anatomy-saas-extraction-AS0002`
**Location:** `C:\Users\bruke\festival-project\festivals\planning\anatomy-saas-extraction-AS0002\`
**Status:** `fest validate` → **VALIDATION PASSED** (structure · completeness · task files · quality gates · 0 markers · ordering all green)

**Goal:** lift `anatomy-map` from a Claude skill into a standalone GitHub App that posts a living architecture diagram on every PR.

| Seq | Working dir | Purpose | Key tasks (each cites real `file:line` evidence) |
|-----|-------------|---------|--------------------------------------------------|
| **01 compiler core** | `packages/compiler` | Deterministic JSX→anatomy compiler (the moat, LLM-free) | jsx region extractor · backend chain detector · template filler + bundler |
| **02 llm polish layer** | `packages/polish` | Thin, swappable LLM names + mockup; degrades gracefully | region naming + mockup fidelity behind `LlmClient` |
| **03 github app saas shell** | `apps/github-app` + `apps/viewer` | Living diagrams on PRs + permissioned hosted viewer | github app PR worker · hosted viewer + auth |

**Dependency order:** 01 is the root → 02 and 03 consume it → 03 also consumes 02.
**Proof-gated done** examples: compiler output byte-identical across runs (determinism); mockup classNames equal source classNames; PR comment count = 1 on re-push; 403 without source-repo read access.
**Evidence base:** all tasks grounded in first-hand recon of `~/.claude/skills/anatomy-map/` (`build.py` bundler, `template.html` 19 KB renderer, `SKILL.md` heuristics at lines 29-45, 48-70, 73-94).
**Note:** scaffold-target dirs created as placeholders under `festival-project` so fest tracking resolves — **decide the real repo location before execution** (a sellable SaaS shouldn't nest inside the festival workspace).

---

## TODAY vs THIS AFTERNOON

### Ship today (Tier 1)
1. **`anatomy-map`** — plan is ready; execute sequence 01 (compiler core). This is the realistic "ship the spine" target for one day.
2. **`delta-scp`** & **`search-stack`** — already running services; "shipping" = wrap a UI + hosting (lighter lift, no rebuild). Need a quick groundwork plan each.
3. **`code-recon`/`verified-audit`** — needs its own groundwork plan first (no backing code yet).

> Honest scope note: a real "ship" of `anatomy-map` in one day = sequence 01 working end-to-end (a `.tsx` file → a correct diagram, LLM-free). The GitHub App shell (seq 03) is a second-day target. Don't promise all four products live by tonight — promise the anatomy-map spine + UI wrappers on the two existing services.

### This afternoon (revisit with creativity)
- The **Tier 3 parking lot** above — work the "creative angle" column. Best candidates for a creative save: the **migration-as-a-service** idea (three-js-migrate / anime-js-migrate already hold the breakage knowledge) and **jargonize** as a viral consumer toy.
- Decide which Tier 3 items get a real wedge vs. stay personal tools.

---

## Next actions
- [ ] Pick the real repo home for the anatomy-map SaaS (not inside `festival-project`).
- [ ] `/groundwork verify` each task's DoD as it's built; promote the festival to active.
- [ ] Spin a quick groundwork plan for `delta-scp` UI and `search-stack` UI (existing services → ship faster).
- [ ] Afternoon: creativity pass on the Tier 3 parking lot.
