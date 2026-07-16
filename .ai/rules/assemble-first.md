# Assemble First, Don't Generate

## The stance

The default build posture is **assembler, not generator**. When someone says "build it," that means *assemble the working pieces*, not *write novel implementation*. Generation is the exception that has to be earned, not the default.

This rule fires every time the work touches a standard capability. Surface the library candidate BY NAME before writing any implementation skeleton.

## The solved-category test

Before writing any non-trivial implementation, ask: **is this a solved category?**

If yes, the default is **assemble**: check the relevant registry (npm / PyPI / crates.io / pkg.go.dev) + current docs for the mature, maintained package. Surface what you found — name it, note maintenance/adoption, propose it — *before* generating any implementation.

Treat "what already exists for this" as a required step, not optional.

## Solved categories (non-exhaustive)

| Category | Canonical libraries |
|---|---|
| Graph layout / node-link viz | cytoscape, vis-network, sigma, react-flow, dagre |
| Drag-and-drop / sortable | sortablejs, dnd-kit, react-dnd, interact.js |
| State machines / FSM / statecharts | xstate, robot, @xstate/fsm |
| Parsing (HTML/JSON/AST) | cheerio, jsdom, parse5, lxml, html5lib, babel, acorn |
| Date/time math | date-fns, dayjs, luxon, pendulum, arrow |
| Fuzzy search | fuse.js, minisearch, lunr, whoosh, rapidfuzz |
| Validation schemas | zod, yup, ajv, pydantic, marshmallow |
| Queuing / background jobs | bullmq, agenda, pgboss, celery, rq, dramatiq |
| Scheduling / cron | node-cron, croner, apscheduler |
| Virtualized lists | react-window, react-virtual, virtua |
| Form handling | felte, react-hook-form, valibot |
| Routing | react-router, koa-router, fastapi router, page.js |
| Diffing | jsdiff, diff-match-patch, deepdiff, jsondiff |
| Timeline rendering | vis-timeline, react-calendar-timeline, frappe-gantt |
| DOM templating | lit-html, morphdom, htm |
| HTTP framework | express, fastapi, hono, fastify, flask, starlette |
| ORM / query builder | prisma, drizzle, kysely, sqlalchemy, peewee |
| WebSocket | socket.io, ws, nats-clients |
| Logging | pino, winston, loguru, structlog |
| Caching | lru-cache, cachetools, diskcache |
| Embeddings / vector search | sentence-transformers, faiss, chromadb |
| Clustering / dim-reduction | hdbscan, umap-learn, scikit-learn |
| Text chunking | langchain text-splitters, semantic-text-splitter |
| CLI parsing | click, typer, commander, yargs |
| Progress bars / TUI | rich, tqdm, listr2, ink |

Add to this list as new solved categories surface. The list is not the ceiling.

## The discriminator: worse, or just later?

Before hand-rolling, ask: "If I use the library instead, will the final product be **worse**, or just **finished sooner**?"

- **Worse** — write it yourself. This is your moat.
- **Just sooner** — use the library. This is tax.

If you can't say "the library would make this worse" out loud and mean it, the hand-roll is unjustified.

## No false symmetry

**Never present a hand-rolled implementation and an established library as equivalent options.** They are not peers. A 150-line hand-roll and a maintained library that solves the same category are not "Option A vs Option B" — one is the real answer, the other is debt that looks stable now and rots over time.

When presenting choices: say which is the real answer and why. If a hand-roll is being floated only because it's faster to type right now, say that explicitly so the tradeoff is visible. Do not launder a shortcut as a neutral choice.

## When hand-rolling actually earns it

Build from scratch ONLY when one of these is true:

1. **No mature option exists** for the capability.
2. **Integration depth is the product value** — the determinism, doctrine fidelity, or tight coupling is the *whole reason this layer exists*, and a generic library would make the product *worse*, not just later.

If you're about to hand-roll and neither condition is clearly met, stop and surface the library option instead.

## Origin

2026-05-29, after a lattice-graph build session where hand-rolling SVG node-link rendering was the default. Pushback: *"do we need to code a graph — isn't there graph software or code that already exists?"* Cytoscape.js was the answer.

Subsequent dogfood audit confirmed the pattern: solved-category hand-rolls appeared in delta-kernel Mode FSM, inPACT step-toggling, and others. The audit also confirmed the instinct was already firing in some places (lattice already vendored Cytoscape before the doctrine was named). This rule names the pattern so it fires consistently.
