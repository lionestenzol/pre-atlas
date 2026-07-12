# inPACT — Supabase setup (block B)

Everything code-shaped for block B is done: the schema, the RLS policies, and
the leak test. What's left needs your Supabase account — I can't create a
project or run SQL against infrastructure I don't have credentials for.

## 1. Create the project

1. https://supabase.com/dashboard → New project.
2. Note the **Project URL** and, under Project Settings → API, the **anon
   public key** and the **service_role key** (service_role is secret — never
   ship it to the browser).

## 2. Apply the schema

SQL editor → paste the contents of `migrations/006_inpact_mvp.sql` (repo
root) → Run. It's idempotent, safe to re-run if you tweak it.

Sanity check in the Table Editor: `app_state` and `entitlements` should both
show a lock icon (RLS enabled) with one policy each.

## 3. Prove RLS actually blocks cross-user access

Don't trust the lock icon alone — run the real test:

```bash
cd apps/inpact/supabase
npm install
export SUPABASE_URL=https://YOUR-PROJECT.supabase.co
export SUPABASE_ANON_KEY=your-anon-key
export SUPABASE_SERVICE_KEY=your-service-role-key   # server-side only, never in the browser
npm run test:rls
```

Before running: Authentication → Providers → Email → turn **off** "Confirm
email" (the test creates users and needs them immediately usable). Turn it
back on before you accept real signups.

Expected: `✅ ALL PASS — 8 passed, 0 failed`. It creates two throwaway users,
proves user B cannot read, list, or overwrite user A's `app_state` row, and
cannot read or self-grant an `entitlements` row. It deletes both test users
on exit whether it passes or fails.

If anything fails here, stop — do not proceed to block C with broken RLS.

## 4. Wire up the browser config

```bash
cp apps/inpact/js/config.example.js apps/inpact/js/config.js
```

Fill in `SUPABASE_URL` and `SUPABASE_ANON_KEY` (anon key only — it's the
`config.js` gitignore entry that keeps this out of the shared repo, not
secrecy of the key itself; RLS is the real boundary). Leave
`STRIPE_PUBLISHABLE_KEY` blank until block F.

`js/storage.js` now exports `SupabaseAdapter` alongside `LocalStorageAdapter`
— it takes an authenticated Supabase client + user id and speaks the same
`load/save/clear` contract. It is not wired into the app yet; block C (auth)
creates the client and session, and block D is what actually swaps the live
adapter after sign-in.

## What "done" looks like for this block

- [ ] Project created, schema applied (step 2)
- [ ] `npm run test:rls` passes 8/8 (step 3)
- [ ] `js/config.js` exists locally with real values (step 4, gitignored)

Once those three are checked, block C (auth) can start.
