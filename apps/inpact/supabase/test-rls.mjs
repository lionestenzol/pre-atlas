#!/usr/bin/env node
// inPACT — RLS cross-user leak test
//
// Proves the gate from SPEC_MVP_36H.md block B: "select blocked cross-user
// (RLS proven)". Creates two throwaway users, writes state as user A, then
// signs in as user B and asserts B cannot read or overwrite A's row — even
// though both go through the same anon client, same table, same code path.
//
// This must be run against a real Supabase project with migration
// 006_inpact_mvp.sql already applied. It is NOT a mock — a green run here is
// the actual proof, not a stand-in for one.
//
// Setup:
//   1. Create a Supabase project (or use an existing one).
//   2. Run migrations/006_inpact_mvp.sql in the SQL editor (or via psql).
//   3. Project Settings -> API: copy the Project URL, anon key, and
//      service_role key.
//   4. export SUPABASE_URL=https://xxxx.supabase.co
//      export SUPABASE_ANON_KEY=...
//      export SUPABASE_SERVICE_KEY=...
//   5. In Authentication -> Providers -> Email, confirm "Confirm email" is
//      OFF for this test (or the created users won't be immediately usable).
//      Turn it back on before going to production auth.
//   6. cd apps/inpact/supabase && npm install && node test-rls.mjs
//
// Cleans up both test users on exit (pass or fail).

import { createClient } from '@supabase/supabase-js';

const URL = process.env.SUPABASE_URL;
const ANON_KEY = process.env.SUPABASE_ANON_KEY;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;

if (!URL || !ANON_KEY || !SERVICE_KEY) {
  console.error('Set SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY first. See header comment.');
  process.exit(1);
}

const admin = createClient(URL, SERVICE_KEY, { auth: { persistSession: false } });

const stamp = Date.now();
const userA = { email: `inpact-rls-test-a-${stamp}@example.com`, password: 'test-pass-A-1234!' };
const userB = { email: `inpact-rls-test-b-${stamp}@example.com`, password: 'test-pass-B-1234!' };

let pass = 0, fail = 0;
const ok = (name, cond) => {
  if (cond) { pass++; console.log('  ✓', name); }
  else { fail++; console.log('  ✗ FAIL:', name); }
};

let createdIds = [];

async function createConfirmedUser(creds) {
  const { data, error } = await admin.auth.admin.createUser({
    email: creds.email,
    password: creds.password,
    email_confirm: true,
  });
  if (error) throw error;
  createdIds.push(data.user.id);
  return data.user.id;
}

async function signInClient(creds) {
  const client = createClient(URL, ANON_KEY, { auth: { persistSession: false } });
  const { error } = await client.auth.signInWithPassword(creds);
  if (error) throw error;
  return client;
}

async function main() {
  console.log('inPACT RLS test — creating two throwaway users...');
  const idA = await createConfirmedUser(userA);
  const idB = await createConfirmedUser(userB);

  const clientA = await signInClient(userA);
  const clientB = await signInClient(userB);

  // A writes their own row.
  const { error: writeErr } = await clientA
    .from('app_state')
    .upsert({ user_id: idA, state: { marker: 'belongs-to-A' } });
  ok('A can write their own app_state row', !writeErr);

  // A can read it back.
  const { data: aReadsOwn, error: aReadOwnErr } = await clientA
    .from('app_state').select('state').eq('user_id', idA).maybeSingle();
  ok('A can read their own row', !aReadOwnErr && aReadsOwn?.state?.marker === 'belongs-to-A');

  // B tries to read A's row directly by id — RLS should return no rows, not an error.
  const { data: bReadsA, error: bReadErr } = await clientB
    .from('app_state').select('state').eq('user_id', idA).maybeSingle();
  ok('B reading A\'s row by id returns no data (RLS silently filters)', !bReadErr && bReadsA === null);

  // B tries to read ALL rows with no filter — should only ever see B's own (none yet).
  const { data: bReadsAll, error: bReadAllErr } = await clientB.from('app_state').select('state');
  ok('B\'s unfiltered select never includes A\'s row', !bReadAllErr && (bReadsAll ?? []).every(r => r.state?.marker !== 'belongs-to-A'));

  // B tries to overwrite A's row (impersonation via WITH CHECK).
  const { error: bWriteErr } = await clientB
    .from('app_state').upsert({ user_id: idA, state: { marker: 'HIJACKED-BY-B' } });
  ok('B cannot write into A\'s row (WITH CHECK blocks it)', !!bWriteErr);

  // Confirm A's row is untouched by B's attempt.
  const { data: aReadsAfter } = await clientA
    .from('app_state').select('state').eq('user_id', idA).maybeSingle();
  ok('A\'s row is unmodified after B\'s attempted hijack', aReadsAfter?.state?.marker === 'belongs-to-A');

  // entitlements: B cannot see A's entitlement row either (seed one via admin first).
  await admin.from('entitlements').upsert({ user_id: idA, tier: 'pro', status: 'active' });
  const { data: bReadsEntitlement, error: bEntErr } = await clientB
    .from('entitlements').select('tier').eq('user_id', idA).maybeSingle();
  ok('B cannot read A\'s entitlement row', !bEntErr && bReadsEntitlement === null);

  // B cannot grant themselves Pro directly (no INSERT/UPDATE policy for entitlements).
  const { error: bSelfGrantErr } = await clientB
    .from('entitlements').upsert({ user_id: idB, tier: 'pro', status: 'active' });
  ok('B cannot self-grant Pro tier (no write policy on entitlements)', !!bSelfGrantErr);

  console.log(`\n${fail === 0 ? '✅ ALL PASS' : '❌ FAILURES'} — ${pass} passed, ${fail} failed`);
}

main()
  .catch((e) => { console.error('Test run errored:', e); fail++; })
  .finally(async () => {
    for (const id of createdIds) {
      await admin.auth.admin.deleteUser(id).catch(() => {});
    }
    await admin.from('app_state').delete().in('user_id', createdIds).then(() => {}, () => {});
    await admin.from('entitlements').delete().in('user_id', createdIds).then(() => {}, () => {});
    console.log('Cleaned up test users.');
    process.exit(fail === 0 ? 0 : 1);
  });
