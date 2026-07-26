/**
 * Atlas Consolidation — Fable orchestration script (DO NOT auto-run; launch deliberately)
 * =====================================================================================
 * Pairs with: ATLAS_CONSOLIDATION_PRESEARCH.md (map) · ATLAS_CONSOLIDATION_RUNBOOK.md (itinerary)
 *             · fest atlas-consolidation-AC0002 (the what).
 *
 * HOW TO LAUNCH (only when you mean to spend tokens):
 *   Open a session on the Fable model, then call the Workflow tool with:
 *     { scriptPath: "C:/Users/bruke/Pre Atlas/atlas-consolidation.workflow.js" }
 *   Optionally cap spend from your prompt (e.g. "+400k") — the script reads budget.remaining()
 *   and stops cleanly at the floor instead of blowing the target.
 *
 * THE MODEL:
 *   - Fable (this main loop + the recon/reason agents) LOOKS and REASONS. It never writes code.
 *   - Each task runs a 3-step chain:  recon+reason (Fable tier) -> execute (Haiku|Sonnet) -> verify.
 *   - Verify proves the task's tool-provable Done-When before it counts as done.
 *   - GATE tasks (3.3, 3.4) self-skip — they wait on your two deferred decisions.
 *
 * KNOBS (below): REASON_MODEL (who does the looking), BUDGET_FLOOR (when to stop).
 */

export const meta = {
  name: 'atlas-consolidation-run',
  description: 'Fable-orchestrated execution of fest atlas-consolidation-AC0002: Fable reasons via recon tools, Haiku/Sonnet execute, verify proves each Done-When. Wave-ordered, budget-guarded, never auto-runs.',
  phases: [
    { title: 'Wave 0 · litter' },
    { title: 'Wave 1 · visibility' },
    { title: 'Wave 2 · maps' },
    { title: 'Wave 3 · harness' },
  ],
}

// ---- KNOBS -----------------------------------------------------------------
// REASON_MODEL: who does the LOOK+REASON step. null = inherit the session model
// (Fable, when you launch in a Fable session — this is what you asked for).
// Set to 'sonnet' to make recon cheaper and reserve Fable only for the GATE decisions.
const REASON_MODEL = null
// Stop before starting a new wave if the token target has this little left.
const BUDGET_FLOOR = 60_000

const FEST = 'C:/Users/bruke/festival-project/festivals/planning/atlas-consolidation-AC0002/001_IMPLEMENT'
const REPO = 'C:/Users/bruke/Pre Atlas'

// Wave selection: pass args {waves:["0"]} to run only Wave 0 (check-in-per-wave mode).
// Omit args to run all four. Re-launch with resumeFromRunId + more waves to continue —
// completed agent calls replay from cache, so nothing re-executes.
const RUN = new Set((args && args.waves) || ['0', '1', '2', '3'])

// ---- THE ITINERARY (from ATLAS_CONSOLIDATION_RUNBOOK.md routing.json) -------
// hands = executor tier for the DO step. mode 'gate' = parked on a deferred decision.
const T = {
  // Wave 0 — litter (fully parallel, zero code risk)
  '0.1': { title: 'root litter sweep',            file: '01_wave0_litter/01_root_litter_sweep.md',                  eyes: 'es + git status',                              hands: 'haiku',  mode: 'do' },
  '0.2': { title: 'gitignore generated blobs',    file: '01_wave0_litter/02_gitignore_generated_blobs.md',          eyes: 'git check-ignore',                             hands: 'haiku',  mode: 'do' },
  '0.3': { title: 'reap orphan processes',        file: '01_wave0_litter/03_reap_orphan_processes.md',              eyes: 'Get-NetTCPConnection + Win32_Process cmdline', hands: 'sonnet', mode: 'do' },
  '0.4': { title: 'fix optogon audit task',       file: '01_wave0_litter/04_fix_optogon_audit_task.md',             eyes: 'Get-ScheduledTask',                            hands: 'haiku',  mode: 'do' },
  // Wave 1 — visibility (parallel; 1.2 reasons before executing)
  '1.1': { title: 'daemon on/off switch',         file: '02_wave1_visibility/01_daemon_on_off_switch.md',           eyes: 'code-recon locate server.ts:81',               hands: 'sonnet', mode: 'do' },
  '1.2': { title: 'dedup morning pipeline',       file: '02_wave1_visibility/02_dedup_morning_pipeline.md',         eyes: 'code-recon trace run_daily.py vs cycleboard_push.py', hands: 'sonnet', mode: 'do' },
  '1.3': { title: 'unified status surface',       file: '02_wave1_visibility/03_unified_status_surface.md',         eyes: 'code-recon status_atlas.ps1 + atlas_status',   hands: 'sonnet', mode: 'do' },
  '1.4': { title: 'rationalize launch/terminal',  file: '02_wave1_visibility/04_rationalize_launch_and_terminal_spam.md', eyes: 'code-recon read start.bat files',        hands: 'sonnet', mode: 'do' },
  // Wave 2 — maps (ordered chain 2.1->2.2->2.3; 2.4 parallel)
  '2.1': { title: 'canonical inventory',          file: '03_wave2_maps/01_canonical_inventory_generator.md',        eyes: 'delta-scp shape + code-recon build_system_index.py', hands: 'sonnet', mode: 'do' },
  '2.2': { title: 'collapse map/wall forks',      file: '03_wave2_maps/02_collapse_map_and_wall_copies.md',         eyes: 'code-recon confirm root reads live',           hands: 'haiku',  mode: 'do' },
  '2.3': { title: 'point views at gateway',       file: '03_wave2_maps/03_point_views_at_gateway.md',               eyes: 'code-recon gateway endpoints',                 hands: 'sonnet', mode: 'do' },
  '2.4': { title: 'quarantine dead scaffolding',  file: '03_wave2_maps/04_quarantine_dead_scaffolding.md',          eyes: 'code-recon prior-art (es machine-wide)',       hands: 'sonnet', mode: 'do' },
  // Wave 3 — harness (3.1/3.2 do; 3.3/3.4 gated on decisions #1/#4)
  '3.1': { title: 'enable ui invocation',         file: '04_wave3_harness/01_enable_ui_invocation.md',              eyes: 'code-recon gateway.py 422 path',               hands: 'sonnet', mode: 'do' },
  '3.2': { title: 'refresh docs to 40 surfaces',  file: '04_wave3_harness/02_refresh_docs_to_real_surface_count.md', eyes: 'atlas_describe_list()',                        hands: 'haiku',  mode: 'do' },
  '3.3': { title: 'resolve two-repo split',       file: '04_wave3_harness/03_resolve_two_repo_split.md',            eyes: 'groundwork brownfield C:/Users/bruke/atlas',   hands: 'sonnet', mode: 'gate', decision: '#1 merge/declare/retire' },
  '3.4': { title: 'finish or shelve partials',    file: '04_wave3_harness/04_finish_or_shelve_partials.md',         eyes: 'code-recon each partial',                      hands: 'sonnet', mode: 'gate', decision: 'finish-vs-shelve per service' },
}

// ---- SCHEMAS (force structured returns, no parsing) ------------------------
const BRIEF_SCHEMA = {
  type: 'object',
  properties: {
    ready: { type: 'boolean', description: 'true if a worker can execute without further discovery' },
    change_spec: { type: 'string', description: 'exact edits/commands for the executor — no ambiguity' },
    files: { type: 'array', items: { type: 'string' }, description: 'file:line targets confirmed at HEAD' },
    done_when: { type: 'string', description: 'the tool-provable check that proves the task is done' },
    blocked_reason: { type: 'string', description: 'why ready=false (drifted anchor / needs a decision), else empty' },
  },
  required: ['ready', 'change_spec', 'files', 'done_when', 'blocked_reason'],
}
const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    proven: { type: 'boolean' },
    evidence: { type: 'string', description: 'the command run and its output' },
    gaps: { type: 'string', description: 'what is still unproven, else empty' },
  },
  required: ['proven', 'evidence', 'gaps'],
}

// ---- AGENT PROMPTS ---------------------------------------------------------
const reconPrompt = (id, t) => `RECON + REASON for fest task ${id} "${t.title}" (Atlas consolidation).
Authoritative task file (read it first): ${FEST}/${t.file}
LOOK using the recon ladder for this task — ${t.eyes}. Prefer the code-recon / delta-scp / groundwork skills if available; otherwise run the underlying tools directly (es, rg, ast-grep/sg, jq, git, Read) from ${REPO}.
VERIFY every file:line the task cites still exists at HEAD — anchors drift; confirm, do not trust the doc.
Produce a change spec a ${t.hands} worker can execute WITHOUT any further discovery: exact files, exact edits/commands, and the task's tool-provable Done-When.
Make NO changes yourself. If a cited anchor is gone or the task needs a deferred decision, set ready=false with blocked_reason.`

const execPrompt = (id, t, brief) => `EXECUTOR for fest task ${id} "${t.title}". Make ONLY the change in this vetted brief — no scope expansion, no drive-by edits.
CHANGE SPEC: ${brief.change_spec}
FILES: ${(brief.files || []).join(', ')}
Work in ${REPO}. Follow code-as-furniture (fix, never document-and-leave). Report exactly what you changed (files + one-line diff summary) so it can be checked against the Done-When: ${brief.done_when}`

const verifyPrompt = (id, t, brief) => `VERIFY step for fest task ${id} "${t.title}" — /groundwork verify discipline.
DONE-WHEN: ${brief.done_when}
Run the exact tool-provable check (grep result / port scan / file count / passing test) from ${REPO}. Cite the command and its raw output.
Return proven=true ONLY if the evidence is unambiguous; otherwise proven=false with the gap.`

// ---- THE PER-TASK CHAIN ----------------------------------------------------
async function runTask(id, phaseTitle) {
  const t = T[id]
  if (t.mode === 'gate') {
    log(`⏸️  [${id}] ${t.title} — PARKED (decision ${t.decision}). Skipping until answered.`)
    return { id, status: 'parked', decision: t.decision }
  }
  // 1. LOOK + REASON — Fable tier (or REASON_MODEL). This is the only "thinking".
  const brief = await agent(reconPrompt(id, t), { label: `recon:${id}`, phase: phaseTitle, schema: BRIEF_SCHEMA, ...(REASON_MODEL ? { model: REASON_MODEL } : {}) })
  if (!brief) return { id, status: 'recon-failed' }
  if (!brief.ready) { log(`🚧 [${id}] not ready: ${brief.blocked_reason}`); return { id, status: 'not-ready', reason: brief.blocked_reason } }
  // 2. DELEGATE — cheap tier does the actual work.
  const work = await agent(execPrompt(id, t, brief), { label: `do:${id}`, phase: phaseTitle, model: t.hands })
  if (!work) return { id, status: 'exec-failed', brief }
  // 3. VERIFY — prove the Done-When before it counts.
  const verdict = await agent(verifyPrompt(id, t, brief), { label: `verify:${id}`, phase: phaseTitle, schema: VERDICT_SCHEMA })
  const status = verdict && verdict.proven ? 'done' : 'unverified'
  log(`${status === 'done' ? '✅' : '⚠️'} [${id}] ${t.title} — ${status}`)
  return { id, status, doneWhen: brief.done_when, evidence: verdict ? verdict.evidence : null, gaps: verdict ? verdict.gaps : null }
}

function canProceed(wave) {
  if (budget.total && budget.remaining() < BUDGET_FLOOR) {
    log(`⛔ budget floor (${Math.round(BUDGET_FLOOR / 1000)}k) hit before ${wave} — ${Math.round(budget.remaining() / 1000)}k left. Stopping cleanly; relaunch to resume.`)
    return false
  }
  return true
}

// ---- WAVES -----------------------------------------------------------------
const results = []

// Wave 0 — fully parallel, zero code risk.
phase('Wave 0 · litter')
if (RUN.has('0') && canProceed('Wave 0')) {
  const r = await parallel(['0.1', '0.2', '0.3', '0.4'].map(id => () => runTask(id, 'Wave 0 · litter')))
  results.push(...r.filter(Boolean))
}

// Wave 1 — visibility (parallel within wave).
phase('Wave 1 · visibility')
if (RUN.has('1') && canProceed('Wave 1')) {
  const r = await parallel(['1.1', '1.2', '1.3', '1.4'].map(id => () => runTask(id, 'Wave 1 · visibility')))
  results.push(...r.filter(Boolean))
}

// Wave 2 — maps. Ordered chain 2.1 -> 2.2 -> 2.3 (each depends on prior); 2.4 runs in parallel.
phase('Wave 2 · maps')
if (RUN.has('2') && canProceed('Wave 2')) {
  const chain = (async () => {
    const a = await runTask('2.1', 'Wave 2 · maps')
    const b = await runTask('2.2', 'Wave 2 · maps')
    const c = await runTask('2.3', 'Wave 2 · maps')
    return [a, b, c]
  })()
  const par = runTask('2.4', 'Wave 2 · maps')
  const [chainRes, parRes] = await Promise.all([chain, par])
  results.push(...chainRes.filter(Boolean), parRes)
}

// Wave 3 — harness. 3.1/3.2 execute; 3.3/3.4 self-park on your deferred decisions.
phase('Wave 3 · harness')
if (RUN.has('3') && canProceed('Wave 3')) {
  const r = await parallel(['3.1', '3.2', '3.3', '3.4'].map(id => () => runTask(id, 'Wave 3 · harness')))
  results.push(...r.filter(Boolean))
}

// ---- REPORT ----------------------------------------------------------------
const tally = results.reduce((m, r) => { m[r.status] = (m[r.status] || 0) + 1; return m }, {})
log(`Atlas consolidation run finished. Tally: ${JSON.stringify(tally)}`)
log('Remember: mark verified tasks done in the fest — from the festival dir, run `fest task complete` per proven task, or reconcile against this report.')
return { festival: 'atlas-consolidation-AC0002', tally, results }
