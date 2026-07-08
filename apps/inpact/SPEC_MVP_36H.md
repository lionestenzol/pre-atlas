# inPACT — 36-Hour "Sellable MVP" Spec

**Author:** Bruke (brukev@gmail.com)
**Date:** 2026-07-08
**Target:** Turn the working CycleBoard/inPACT app into a paid, multi-user product in one 36-hour sprint.
**Branch:** `claude/36-hour-code-challenge-q99evc`

---

## 0. One-paragraph thesis

inPACT already works: ~6,000 LOC of vanilla JS, 17 screens, real task/day/routine/journal/reflection workflows, persisted to `localStorage`. The MVP is **not a rewrite** — it is three pieces of plumbing bolted onto a product that already runs: (1) accounts, (2) cloud persistence, (3) payment + entitlement gating. Everything sellable about it — a working execution tool tied to an existing 20-lesson curriculum audience — is already true today. This sprint makes it *usable by someone who isn't you, on a second device, behind a paywall.*

The build is deliberately additive. If Supabase or Stripe is ripped out, the app must still boot on `localStorage`. That constraint is what keeps 36 hours realistic.

---

## 1. Scope

### In scope (must ship)
1. **Storage abstraction** — a `StorageAdapter` interface; `localStorage` and Supabase are two implementations. App code never calls storage directly.
2. **Auth** — Supabase email magic-link sign-in. Anonymous/local mode still works (no account required to try it).
3. **Cloud persistence** — per-user state in Supabase with row-level security. Debounced save, load-on-login, local→cloud migration on first sign-in.
4. **Paywall** — Stripe Checkout (subscription), webhook → entitlement state, three enforced free-tier limits.
5. **Entitlement gating** — free vs. paid enforced in the UI at the three boundaries below.
6. **Deploy** — the app served at a real URL (static host) with the Supabase edge function / webhook reachable.

### Out of scope (explicit cut lines — do NOT build this weekend)
- Public integrity share links / witness identity (roadmap §6) — **stretch only**, after everything else is green.
- Onboarding 5-screen walkthrough (roadmap §4) — **reduced** to a single welcome + tier-preview screen; full curriculum onboarding is post-MVP.
- Schema normalization — state is stored as one JSONB blob per user (roadmap explicitly allows "mirror the current `state.js` shape"). Normalize later, never this weekend.
- Marketing site — out. Signup deep-link (`?lesson=N`) is read if present, otherwise ignored.
- Team/collaboration, offline conflict resolution beyond last-write-wins, mobile-native.

---

## 2. Current state (what exists, verified)

| Piece | Reality |
|---|---|
| App | `apps/inpact/` — static, no build step, Tailwind + Font Awesome via CDN |
| Code | `js/` — `state.js` (429), `functions.js` (2953), `screens.js` (1047), `signals.js` (394), `today.js` (293), `helpers.js` (270), `ui.js` (259), `validator.js` (225), `api.js` (100), `app.js` (30) |
| Persistence | `CycleBoardState` class in `state.js` → `localStorage`, single payload, debounced save, 50-step undo history |
| State shape | `version, screen, AZTask[], DayPlans{}, FocusArea[], Routine{}, DayTypeTemplates{}, Journal, EightSteps, Reflections` |
| Run | `http-server` on port 3006 (`inpact-app` launch config) |

**Key implication:** persistence is already centralized in one class (`CycleBoardState`). That is the single seam we widen. We do **not** touch the 2,953-line `functions.js`.

---

## 3. Target architecture

```
Browser (static app, unchanged UI)
  └─ CycleBoardState  ── uses ──▶  StorageAdapter (interface)
                                     ├─ LocalStorageAdapter   (existing behavior)
                                     └─ SupabaseAdapter        (auth-gated cloud)
  └─ AuthController  ── Supabase Auth (magic link)
  └─ EntitlementGate ── reads entitlement cache, gates 3 UI paths

Supabase
  ├─ auth.users
  ├─ app_state   (user_id PK/FK, state jsonb, updated_at)   [RLS: owner-only]
  ├─ entitlements(user_id PK/FK, tier, status, stripe_customer_id, current_period_end) [RLS: owner read]
  └─ edge function: stripe-webhook  (service role → writes entitlements)

Stripe
  ├─ Checkout Session (subscription)
  └─ Webhook → Supabase edge function
```

**Non-negotiable invariant:** the app boots and is fully usable with Supabase/Stripe env vars absent → it silently falls back to `LocalStorageAdapter` and free tier. This makes every later phase independently testable and keeps a demo alive even if a key is wrong.

---

## 4. Data model

### 4.1 `app_state`
```sql
create table app_state (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  state      jsonb not null,          -- mirror of CycleBoardState.state
  version    text  not null default '2.0',
  updated_at timestamptz not null default now()
);
alter table app_state enable row level security;
create policy "own state" on app_state
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
```
`state` is the exact `getDefaultState()` shape. No per-field columns. Conflict policy: **last write wins**, guarded by `updated_at` compare on load.

### 4.2 `entitlements`
```sql
create table entitlements (
  user_id             uuid primary key references auth.users(id) on delete cascade,
  tier                text not null default 'free',   -- 'free' | 'pro'
  status              text not null default 'inactive',-- stripe subscription status
  stripe_customer_id  text,
  current_period_end  timestamptz,
  updated_at          timestamptz not null default now()
);
alter table entitlements enable row level security;
create policy "own entitlement read" on entitlements
  for select using (auth.uid() = user_id);
-- writes happen only via service-role edge function (bypasses RLS)
```
The client **reads** entitlement to render access. It never writes it. Stripe is the source of truth; the webhook is the only writer.

---

## 5. Storage abstraction (Phase 1 — do first)

Add to `state.js`, above `CycleBoardState`:

```js
// StorageAdapter contract
// load()        -> Promise<stateObject | null>
// save(state)   -> Promise<void>
// clear()       -> Promise<void>
// isRemote      -> boolean
```

- Extract current `loadFromStorage`/`saveToStorage` bodies into `LocalStorageAdapter`.
- `CycleBoardState` gets an injected adapter, default `LocalStorageAdapter`.
- All existing sync calls become `await`-tolerant (wrap load in an async init; keep a synchronous in-memory `this.state` so `functions.js` is untouched — it reads/writes `this.state` and calls `save()`, which becomes fire-and-forget debounced).

**Acceptance:** app behaves identically to today with `LocalStorageAdapter`. Zero UI change. This phase ships before any network code.

---

## 6. Auth (Phase 2)

- Add Supabase JS via CDN (keeps no-build constraint).
- `AuthController`: `signInWithOtp(email)`, `onAuthStateChange`, `signOut`, `getUser`.
- UI: a single sign-in modal (email field → "check your inbox"). A header account chip (email + sign out).
- **Try-before-signup:** unauthenticated users get the full app on `LocalStorageAdapter`, free tier. A persistent "Sign in to sync" affordance.
- On sign-in: instantiate `SupabaseAdapter`, run migration (§7), swap the live adapter.

## 7. Cloud persistence + migration (Phase 3)

- `SupabaseAdapter.load()` → `select state from app_state where user_id = uid`.
- `SupabaseAdapter.save(state)` → `upsert` with `updated_at = now()`; debounced (reuse existing `saveDebounceTimer`, ~800 ms).
- **First-login migration:** if cloud row is empty and local state is non-default, push local → cloud, then mark local as migrated. If both exist, newest `updated_at` wins; the loser is kept in a `localStorage` backup key for safety.
- Load order on boot: if session → cloud; else local.

**Acceptance:** sign in on machine A, add a task, sign in on machine B → task appears. Sign out → local free-tier app still works.

## 8. Paywall + entitlement (Phase 4)

### 8.1 Free-tier limits (from roadmap §5 — enforce exactly these three)
| Feature | Free | Pro |
|---|---|---|
| A–Z expansion | ≤ 5 letters | unlimited |
| Reflections | weekly only | weekly + monthly + quarterly + yearly |
| Active routines | 1 | multiple |

### 8.2 Enforcement
- `EntitlementGate.can(feature, currentCount)` — pure function, single source of gating truth.
- Three call sites only: the A–Z "add letter" action, the reflection-period selector, the "activate routine" action. Each shows an upgrade prompt when blocked.
- Entitlement is cached in memory on load; free if unauthenticated or no row.

### 8.3 Stripe
- "Upgrade" → create Checkout Session (subscription) via a tiny serverless endpoint / Supabase edge function (`create-checkout`), passing `user_id` in `client_reference_id`.
- Webhook edge function (`stripe-webhook`) handles `checkout.session.completed`, `customer.subscription.updated/deleted` → upsert `entitlements` (service role). Verify signature.
- Client refreshes entitlement on return from Checkout and on auth change.

**Acceptance:** free user hits the 6th A–Z letter → upgrade prompt → completes Stripe test-mode checkout → webhook flips tier to `pro` → limit lifts without reload-from-scratch (a refresh is acceptable for MVP).

## 9. Onboarding (reduced)
- One welcome screen after first sign-in: product purpose + a tier-preview card. Reads `?lesson=N` from URL if present to highlight the matching upgrade prompt; otherwise generic. Persist `onboarded: true` in state. Full 5-screen curriculum flow is post-MVP.

## 10. Deployment
- Static app → Vercel/Netlify (repo already has `vercel.json`). Env: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `STRIPE_PUBLISHABLE_KEY` injected at build/runtime as a small `config.js`.
- Supabase: run migrations, deploy 2 edge functions, set `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET` as function secrets.
- Point Stripe webhook at the deployed function URL.

---

## 11. 36-hour timeline

| Block | Hours | Deliverable | Gate to advance |
|---|---|---|---|
| A. Storage abstraction | 0–5 | `StorageAdapter` + `LocalStorageAdapter`, app identical to today | App runs, no regressions |
| B. Supabase project + schema | 5–8 | Tables, RLS, project keys, `config.js` | `select` blocked cross-user (RLS proven) |
| C. Auth | 8–14 | Magic-link sign-in, account chip, try-before-signup | Sign in/out works end-to-end |
| D. Cloud persistence + migration | 14–22 | `SupabaseAdapter`, debounced save, A↔B device sync, local→cloud migration | Two-device sync demo passes |
| E. Entitlement gate | 22–26 | `EntitlementGate`, 3 limits enforced, upgrade prompts | Free limits provably block |
| F. Stripe | 26–33 | Checkout + both edge functions + webhook, tier flip | Test-mode purchase unlocks Pro |
| G. Onboarding + deploy + polish | 33–36 | Welcome screen, deployed URL, smoke test | Public URL does the full loop |

**Buffer discipline:** if any block runs >1.5× its budget, cut to the nearest green state and drop the stretch. Order is dependency-correct: nothing after A can start before A is green.

---

## 12. Definition of Done (acceptance for "sellable MVP")

A stranger, on a fresh browser at the public URL, can:
1. Use the app immediately (no signup wall).
2. Sign in with an email magic link.
3. See their data persist and sync to a second device.
4. Hit a free-tier limit and see an upgrade prompt.
5. Pay via Stripe (test mode) and have the limit lift.
6. Sign out and back in — data intact.

If all six pass on the deployed URL, the MVP is **shippable**. "Sellable" then depends on a real buyer — which is a go-to-market question this spec does not, and cannot, resolve.

---

## 13. Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| `functions.js` (2953 LOC) assumes synchronous storage | High | Keep `this.state` in memory synchronously; only load/save cross the async boundary. Never refactor `functions.js`. |
| Stripe webhook not reachable locally | Med | Use Stripe CLI `listen` in dev; deploy the function early (block F front-loads deploy of the webhook). |
| RLS misconfig leaks data | Med (high impact) | Explicit cross-user `select` test in block B before any real data goes in. |
| Magic-link email deliverability | Med | Use Supabase built-in email for MVP; note custom SMTP as post-MVP. |
| Scope creep into public-share / full onboarding | High | Hard cut lines in §1. Stretch only after §12 is fully green. |
| No-build constraint vs. needing bundled SDKs | Low | Supabase + Stripe both ship browser ESM/CDN builds; keep using CDN. |

---

## 14. Stretch (only if §12 is green with time to spare)
- Public integrity share link per A–Z task (roadmap §6), read-only renderer, no witness identity.
- Full 5-screen curriculum onboarding (roadmap §4).
- Annual plan / pricing table.

---

## 15. Explicit non-promises
- This spec ships **software**, not **demand**. "Sellable" is validated by one paying stranger, not by code merging green.
- Retention, pricing, and curriculum-funnel conversion are out of engineering scope and unaddressed here by design.
