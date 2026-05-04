#!/usr/bin/env tsx
/**
 * Atlas AI CLI — The Blade
 *
 * AI-native JSON CLI for the Atlas governance system.
 * Three layers: Primitives → Compounds → Agent loop.
 * Single file. Zero new dependencies. Thin facade over backend laws.
 *
 * Vendored utilities from atlas.ts (2026-04-10).
 */

import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import * as crypto from 'crypto';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const API = 'http://localhost:3001';
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..', '..');
const BRAIN_DIR = path.resolve(REPO_ROOT, 'services', 'cognitive-sensor', 'cycleboard', 'brain');
const ATLAS_DIR = path.join(os.homedir(), '.atlas');

// ── Output ──

function debug(...args: any[]) {
  if (process.env.ATLAS_DEBUG === '1') console.error('[atlas-ai]', ...args);
}

function respond(data: any, meta?: { degraded?: boolean; sources?: string[]; steps?: number }) {
  const out: any = { ok: true, data };
  if (meta) out.meta = meta;
  process.stdout.write(JSON.stringify(out, null, 2) + '\n');
}

function fail(code: string, message: string, details?: any) {
  const out = { ok: false, error: { code, message, ...(details ? { details } : {}) } };
  process.stdout.write(JSON.stringify(out, null, 2) + '\n');
  process.exit(1);
}

// ── Auth & API ──

let cachedToken: string | null = null;

async function getToken(): Promise<string | null> {
  if (cachedToken) return cachedToken;
  try {
    const res = await fetch(`${API}/api/auth/token`);
    const json = await res.json() as any;
    cachedToken = json.token ?? null;
    return cachedToken;
  } catch { return null; }
}

async function apiFetch(urlPath: string, options: RequestInit = {}): Promise<any> {
  const token = await getToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (options.body) headers['Content-Type'] = 'application/json';
  const res = await fetch(`${API}${urlPath}`, { ...options, headers });
  return res.json();
}

// ── Brain files ──

function readBrainJson(file: string): any {
  try { return JSON.parse(fs.readFileSync(path.join(BRAIN_DIR, file), 'utf-8')); }
  catch { return null; }
}

function readBrainText(file: string): string | null {
  try { return fs.readFileSync(path.join(BRAIN_DIR, file), 'utf-8').trim(); }
  catch { return null; }
}

// ── Lifecycle manifest guard ──
// Returns convo_ids whose harvest manifest is mid-lifecycle (PLANNED, BUILDING,
// REVIEWING) or already terminal (DONE, RESOLVED, DROPPED). Autonomous closers
// must skip these — the human is still working the thread or already finished it.
const MID_LIFECYCLE_STATUSES = new Set(['PLANNED', 'BUILDING', 'REVIEWING', 'DONE', 'RESOLVED', 'DROPPED']);
function midLifecycleIds(): Set<string> {
  const harvestDir = path.resolve(REPO_ROOT, 'services', 'cognitive-sensor', 'harvest');
  const ids = new Set<string>();
  let entries: string[] = [];
  try { entries = fs.readdirSync(harvestDir); } catch { return ids; }
  for (const entry of entries) {
    const manifestPath = path.join(harvestDir, entry, 'manifest.json');
    try {
      const m = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
      if (MID_LIFECYCLE_STATUSES.has(m.status) && m.convo_id != null) {
        ids.add(String(m.convo_id));
      }
    } catch { /* skip unreadable manifests */ }
  }
  return ids;
}

// ── Cycleboard ──

async function getCycleboardState(): Promise<any> {
  const data = await apiFetch('/api/cycleboard');
  return data?.data || {};
}

async function updateCycleboardState(updates: Record<string, any>): Promise<void> {
  const current = await getCycleboardState();
  await apiFetch('/api/cycleboard', { method: 'PUT', body: JSON.stringify({ ...current, ...updates }) });
}

// ── Helpers ──

function todayDate(): string { return new Date().toISOString().slice(0, 10); }

function parseFlag(args: string[], flag: string): string | undefined {
  const idx = args.indexOf('--' + flag);
  return idx >= 0 && idx + 1 < args.length ? args[idx + 1] : undefined;
}

function hasFlag(args: string[], flag: string): boolean {
  return args.includes('--' + flag);
}

function ensureDir(dir: string) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

// ── LLM ──

const LLM_ENDPOINT = process.env.ATLAS_LLM_ENDPOINT || '';
const LLM_MODEL = process.env.ATLAS_LLM_MODEL || 'llama3.1:8b';
const LLM_TIMEOUT = 90_000;
const USER_ATLAS_DIR = path.join(os.homedir(), 'atlas');

async function llmAvailable(): Promise<boolean> {
  if (!LLM_ENDPOINT) return false;
  try {
    const res = await fetch(`${LLM_ENDPOINT}/api/tags`, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch { return false; }
}

async function llmGenerate(prompt: string, system?: string): Promise<string | null> {
  if (!LLM_ENDPOINT) return null;
  try {
    const messages: Array<{ role: string; content: string }> = [];
    if (system) messages.push({ role: 'system', content: system });
    messages.push({ role: 'user', content: prompt });
    const res = await fetch(`${LLM_ENDPOINT}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: LLM_MODEL, messages, max_tokens: 4096 }),
      signal: AbortSignal.timeout(LLM_TIMEOUT),
    });
    if (!res.ok) { debug('llm error:', res.status); return null; }
    const data = await res.json() as any;
    return data.choices?.[0]?.message?.content || null;
  } catch (e: any) { debug('llm failed:', e.message); return null; }
}

// ═══════════════════════════════════════════════════════════════
// LAYER 1 — PRIMITIVES
// ═══════════════════════════════════════════════════════════════

// ── Read: Full State ──

async function getFullStateRaw(fields?: string[]): Promise<{ data: Record<string, any>; meta: { degraded: boolean; sources: string[] } }> {
  const sources: string[] = [];
  let degraded = false;

  let unified: any = null;
  try { unified = await apiFetch('/api/state/unified'); sources.push('unified'); }
  catch { degraded = true; }

  let signals: any = null;
  try { signals = await apiFetch('/api/life-signals'); sources.push('signals'); }
  catch {
    signals = {
      energy: readBrainJson('energy_metrics.json'),
      finance: readBrainJson('finance_metrics.json'),
      skills: readBrainJson('skills_metrics.json'),
      network: readBrainJson('network_metrics.json'),
    };
    if (signals.energy || signals.finance) { sources.push('brain-signals'); degraded = true; }
  }

  let cycleboard: any = null;
  try { cycleboard = await getCycleboardState(); sources.push('cycleboard'); }
  catch { degraded = true; }

  let data: Record<string, any> = {
    mode: unified?.derived?.mode ?? null,
    build_allowed: unified?.derived?.build_allowed ?? null,
    open_loops: unified?.derived?.open_loops ?? null,
    closure_ratio: unified?.derived?.closure_ratio ?? null,
    streak: unified?.derived?.streak_days ?? null,
    directive: unified?.derived?.primary_order ?? null,
    loops: unified?.cognitive?.cognitive_state?.loops ?? [],
    drift: unified?.cognitive?.cognitive_state?.drift ?? null,
    energy: signals?.energy ?? null,
    finance: signals?.finance ?? null,
    skills: signals?.skills ?? null,
    network: signals?.network ?? null,
    day: cycleboard?.DayPlans?.[todayDate()] ?? null,
    routines: cycleboard?.Routine ?? null,
    focus: cycleboard?.FocusArea ?? [],
    health: null,
    strategic: readBrainJson('strategic_priorities.json'),
    governor: readBrainJson('governor_headline.json'),
  };

  if (fields) data = Object.fromEntries(fields.map(f => [f, data[f] ?? null]));
  return { data, meta: { degraded, sources } };
}

// ── Read: Individual ──

async function cmdState(args: string[]) {
  const fields = parseFlag(args, 'fields')?.split(',');
  const { data, meta } = await getFullStateRaw(fields);
  respond(data, meta);
}

async function cmdLoops() {
  const unified = await apiFetch('/api/state/unified').catch(() => null);
  respond(unified?.cognitive?.cognitive_state?.loops ?? []);
}

async function cmdDay(args: string[]) {
  const sub = args[0];
  if (sub === 'create') return cmdDayCreate(args.slice(1));
  if (sub === 'block') return cmdDayBlock(args.slice(1));
  if (sub === 'done') return cmdDayDone(args.slice(1));
  if (sub === 'goal') return cmdDayGoal(args.slice(1));
  if (sub === 'rate') return cmdDayRate(args.slice(1));
  const date = args[0] || todayDate();
  const cb = await getCycleboardState();
  respond(cb?.DayPlans?.[date] ?? null);
}

async function cmdCognitive() {
  const unified = await apiFetch('/api/state/unified').catch(() => null);
  const governor = readBrainJson('governor_headline.json');
  respond({
    mode: unified?.derived?.mode ?? null,
    closure_ratio: unified?.derived?.closure_ratio ?? null,
    drift: unified?.cognitive?.cognitive_state?.drift ?? null,
    loops: (unified?.cognitive?.cognitive_state?.loops ?? []).slice(0, 5),
    drift_score: governor?.drift_score ?? null,
    compliance: governor?.compliance_rate ?? null,
    closure_quality: governor?.closure_quality ?? null,
    warning: governor?.warning ?? null,
    top_move: governor?.top_move ?? null,
  });
}

async function cmdDirective() {
  const unified = await apiFetch('/api/state/unified').catch(() => null);
  const strategic = readBrainJson('strategic_priorities.json');
  const governor = readBrainJson('governor_headline.json');
  respond({
    mode: unified?.derived?.mode ?? null,
    directive: unified?.derived?.primary_order ?? null,
    build_allowed: unified?.derived?.build_allowed ?? null,
    daily_directive: strategic?.daily_directive ?? null,
    top_clusters: strategic?.top_clusters?.slice(0, 3) ?? [],
    governor_warning: governor?.warning ?? null,
    governor_top_move: governor?.top_move ?? null,
    drift_alerts: governor?.drift_alerts ?? [],
  });
}

async function cmdHealth() {
  const data = await apiFetch('/api/services/health').catch(() => null);
  if (!data) return fail('API_DOWN', 'delta-kernel unreachable');
  respond(data);
}

async function cmdOsint() { respond(readBrainJson('osint_feed.json')); }

// ── Write: Signals ──

async function cmdEnergy(args: string[]) {
  if (args.length === 0 || args[0]?.startsWith('--')) {
    const signals = await apiFetch('/api/life-signals').catch(() => null);
    return respond(signals?.energy ?? readBrainJson('energy_metrics.json'));
  }
  const body: Record<string, any> = {};
  if (args[0] && !args[0].startsWith('--')) body.energy_level = parseInt(args[0]);
  const load = parseFlag(args, 'load'); if (load) body.mental_load = parseInt(load);
  const sleep = parseFlag(args, 'sleep'); if (sleep) body.sleep_quality = parseInt(sleep);
  respond((await apiFetch('/api/life-signals/energy', { method: 'POST', body: JSON.stringify(body) })).energy);
}

async function cmdFinance(args: string[]) {
  if (args.length === 0) {
    const signals = await apiFetch('/api/life-signals').catch(() => null);
    return respond(signals?.finance ?? readBrainJson('finance_metrics.json'));
  }
  const body: Record<string, any> = {};
  const r = parseFlag(args, 'runway'); if (r) body.runway_months = parseFloat(r);
  const i = parseFlag(args, 'income'); if (i) body.monthly_income = parseFloat(i);
  const e = parseFlag(args, 'expenses'); if (e) body.monthly_expenses = parseFloat(e);
  respond((await apiFetch('/api/life-signals/finance', { method: 'POST', body: JSON.stringify(body) })).finance);
}

async function cmdSkills(args: string[]) {
  if (args.length === 0) {
    const signals = await apiFetch('/api/life-signals').catch(() => null);
    return respond(signals?.skills ?? readBrainJson('skills_metrics.json'));
  }
  const body: Record<string, any> = {};
  const u = parseFlag(args, 'util'); if (u) body.utilization_pct = parseFloat(u);
  if (hasFlag(args, 'learning')) body.active_learning = true;
  const m = parseFlag(args, 'mastery'); if (m) body.mastery_count = parseInt(m);
  const g = parseFlag(args, 'growth'); if (g) body.growth_count = parseInt(g);
  respond((await apiFetch('/api/life-signals/skills', { method: 'POST', body: JSON.stringify(body) })).skills);
}

async function cmdNetwork(args: string[]) {
  if (args.length === 0) {
    const signals = await apiFetch('/api/life-signals').catch(() => null);
    return respond(signals?.network ?? readBrainJson('network_metrics.json'));
  }
  const body: Record<string, any> = {};
  const c = parseFlag(args, 'collab'); if (c) body.collaboration_score = parseInt(c);
  const r = parseFlag(args, 'relationships'); if (r) body.active_relationships = parseInt(r);
  const o = parseFlag(args, 'outreach'); if (o) body.outreach_this_week = parseInt(o);
  respond((await apiFetch('/api/life-signals/network', { method: 'POST', body: JSON.stringify(body) })).network);
}

// ── Write: Loops ──

async function cmdClose(args: string[]) {
  const id = args[0];
  if (!id) return fail('MISSING_ARG', 'Usage: atlas-ai close <loop_id>');
  respond(await apiFetch('/api/law/close_loop', { method: 'POST', body: JSON.stringify({ loop_id: id, outcome: 'closed', title: 'atlas-ai close', status: 'RESOLVED', artifact_path: null, coverage_score: null }) }));
}

async function cmdArchive(args: string[]) {
  const id = args[0];
  if (!id) return fail('MISSING_ARG', 'Usage: atlas-ai archive <loop_id>');
  respond(await apiFetch('/api/law/close_loop', { method: 'POST', body: JSON.stringify({ loop_id: id, outcome: 'archived', title: 'atlas-ai archive', status: 'DROPPED', artifact_path: null, coverage_score: null }) }));
}

// ── Write: Day Plan ──

async function cmdDayCreate(args: string[]) {
  const dayType = (args[0] || 'A').toUpperCase();
  if (!['A', 'B', 'C'].includes(dayType)) return fail('INVALID_ARG', 'Day type must be A, B, or C');
  const date = todayDate();
  const state = await getCycleboardState();
  if (!state.DayPlans) state.DayPlans = {};
  if (state.DayPlans[date]) return fail('EXISTS', `Plan already exists for ${date}`);
  state.DayPlans[date] = {
    id: Date.now().toString(36), date, day_type: dayType, time_blocks: [],
    baseline_goal: { text: '', completed: false }, stretch_goal: { text: '', completed: false },
    focus_areas: [], routines_completed: {}, notes: '', rating: 0, progress_snapshots: [], final_progress: 0,
  };
  await updateCycleboardState({ DayPlans: state.DayPlans });
  respond({ created: true, date, day_type: dayType });
}

async function cmdDayBlock(args: string[]) {
  const time = args[0]; const title = args.slice(1).join(' ');
  if (!time || !title) return fail('MISSING_ARG', 'Usage: atlas-ai day block <time> <title>');
  const date = todayDate(); const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan) return fail('NO_PLAN', 'No plan for today');
  plan.time_blocks.push({ id: Date.now().toString(36), time, title, completed: false });
  plan.time_blocks.sort((a: any, b: any) => (a.time || '').localeCompare(b.time || ''));
  await updateCycleboardState({ DayPlans: state.DayPlans });
  respond({ added: true, time, title });
}

async function cmdDayDone(args: string[]) {
  const idx = parseInt(args[0]) - 1;
  if (isNaN(idx)) return fail('MISSING_ARG', 'Usage: atlas-ai day done <block#>');
  const date = todayDate(); const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan || !plan.time_blocks[idx]) return fail('NOT_FOUND', 'Block not found');
  plan.time_blocks[idx].completed = true;
  await updateCycleboardState({ DayPlans: state.DayPlans });
  respond({ completed: true, block: plan.time_blocks[idx] });
}

async function cmdDayGoal(args: string[]) {
  const type = args[0]; const text = args.slice(1).join(' ');
  if (!type || !text || !['baseline', 'stretch'].includes(type)) return fail('MISSING_ARG', 'Usage: atlas-ai day goal baseline|stretch <text>');
  const date = todayDate(); const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan) return fail('NO_PLAN', 'No plan for today');
  plan[`${type}_goal`] = { text, completed: false };
  await updateCycleboardState({ DayPlans: state.DayPlans });
  respond({ set: true, type, text });
}

async function cmdDayRate(args: string[]) {
  const rating = parseInt(args[0]);
  if (isNaN(rating) || rating < 1 || rating > 5) return fail('INVALID_ARG', 'Usage: atlas-ai day rate <1-5>');
  const date = todayDate(); const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan) return fail('NO_PLAN', 'No plan for today');
  plan.rating = rating;
  await updateCycleboardState({ DayPlans: state.DayPlans });
  respond({ rated: true, rating });
}

// ── Write: Tasks, Wins, Journal ──

async function cmdTask(args: string[]) {
  if (args[0] === 'add') {
    const title = args.slice(1).join(' ');
    if (!title) return fail('MISSING_ARG', 'Usage: atlas-ai task add <title>');
    const data = await apiFetch('/api/tasks', { method: 'POST', body: JSON.stringify({ title_template: title, title_params: {}, status: 'OPEN', priority: 'NORMAL', due_at: null, linked_thread: null }) });
    return respond({ created: true, id: data?.entity?.entity_id });
  }
  if (args[0] === 'done') {
    const id = args[1]; if (!id) return fail('MISSING_ARG', 'Usage: atlas-ai task done <id>');
    await apiFetch(`/api/tasks/${id}`, { method: 'PUT', body: JSON.stringify([{ op: 'replace', path: '/status', value: 'DONE' }]) });
    return respond({ done: true, id });
  }
  const data = await apiFetch('/api/tasks');
  respond(Array.isArray(data) ? data : data?.tasks ?? []);
}

async function cmdWin(args: string[]) {
  const text = args.join(' ');
  if (!text) return fail('MISSING_ARG', 'Usage: atlas-ai win <text>');
  const state = await getCycleboardState();
  if (!state.MomentumWins) state.MomentumWins = [];
  state.MomentumWins.push({ id: Date.now().toString(36), date: todayDate(), timestamp: new Date().toISOString(), description: text });
  await updateCycleboardState({ MomentumWins: state.MomentumWins });
  respond({ logged: true, text });
}

async function cmdJournal(args: string[]) {
  if (args[0] === 'add') {
    const text = args.slice(1).join(' ');
    if (!text) return fail('MISSING_ARG', 'Usage: atlas-ai journal add <text>');
    const state = await getCycleboardState();
    if (!state.Journal) state.Journal = [];
    state.Journal.push({ id: Date.now().toString(36), date: todayDate(), createdAt: new Date().toISOString(), content: text, mood: null });
    await updateCycleboardState({ Journal: state.Journal });
    return respond({ added: true });
  }
  const state = await getCycleboardState();
  respond((state?.Journal ?? []).slice(-10).reverse());
}

async function cmdRefresh() {
  try {
    const output = execSync('python refresh.py', { cwd: path.resolve(REPO_ROOT, 'services', 'cognitive-sensor'), timeout: 600000, encoding: 'utf-8' });
    respond({ refreshed: true, output: output.trim().split('\n').slice(-5) });
  } catch (e: any) { fail('REFRESH_FAILED', e.message); }
}

// ── Await Queue ──

function awaitPath(): string { return path.join(USER_ATLAS_DIR, 'awaiting_response.json'); }

function loadAwaitQueue(): Array<{ convo_id: string; context: string; tone?: string }> {
  try { return JSON.parse(fs.readFileSync(awaitPath(), 'utf-8')); }
  catch { return []; }
}

function saveAwaitQueue(entries: Array<{ convo_id: string; context: string; tone?: string }>): void {
  ensureDir(USER_ATLAS_DIR);
  fs.writeFileSync(awaitPath(), JSON.stringify(entries, null, 2));
}

function cmdAwait(args: string[]) {
  const sub = args[0];
  if (!sub || sub === 'list') {
    return respond(loadAwaitQueue());
  }
  if (sub === 'add') {
    const convoId = args[1];
    if (!convoId) return fail('MISSING_ARG', 'Usage: await add <convo_id> <context> [--tone T]');
    const tone = parseFlag(args.slice(1), 'tone');
    const contextParts = args.slice(2).filter(a => a !== '--tone' && a !== tone);
    const context = contextParts.join(' ');
    if (!context) return fail('MISSING_ARG', 'Context is required: await add <convo_id> <context>');
    const queue = loadAwaitQueue();
    if (queue.some(e => e.convo_id === convoId)) return fail('DUPLICATE', `Entry "${convoId}" already exists`);
    const entry: { convo_id: string; context: string; tone?: string } = { convo_id: convoId, context };
    if (tone) entry.tone = tone;
    queue.push(entry);
    saveAwaitQueue(queue);
    return respond({ added: true, convo_id: convoId, entries: queue.length });
  }
  if (sub === 'remove') {
    const convoId = args[1];
    if (!convoId) return fail('MISSING_ARG', 'Usage: await remove <convo_id>');
    const queue = loadAwaitQueue();
    const filtered = queue.filter(e => e.convo_id !== convoId);
    if (filtered.length === queue.length) return fail('NOT_FOUND', `No entry with convo_id "${convoId}"`);
    saveAwaitQueue(filtered);
    return respond({ removed: true, convo_id: convoId, remaining: filtered.length });
  }
  if (sub === 'clear') {
    saveAwaitQueue([]);
    return respond({ cleared: true });
  }
  fail('UNKNOWN_SUBCOMMAND', `Unknown: await ${sub}. Use: list|add|remove|clear`);
}

// ── Decision Primitive ──

const MODE_ALLOWED_ACTIONS: Record<string, string[]> = {
  RECOVER:     ['rest', 'health_actions', 'sleep', 'light_admin'],
  CLOSURE:     ['finish_tasks', 'reply_messages', 'clean_queues'],
  MAINTENANCE: ['light_admin', 'health_actions', 'finish_tasks'],
  BUILD:       ['draft_assets', 'plans', 'systems'],
  COMPOUND:    ['extend_assets', 'marketing', 'leverage'],
  SCALE:       ['hiring', 'delegation', 'infrastructure', 'funding'],
};

interface Decision {
  action: string; reason: string; target?: string; command?: string;
  allowed_actions: string[]; mode: string; energy: number | null;
}

function decide(state: Record<string, any>): Decision {
  const mode = state.mode ?? 'RECOVER';
  const energy = state.energy?.energy_level ?? null;
  const loops = [...(state.loops ?? [])].sort((a: any, b: any) => (b.score ?? 0) - (a.score ?? 0));
  const day = state.day;
  const allowed = MODE_ALLOWED_ACTIONS[mode] ?? [];
  const base = { mode, energy, allowed_actions: allowed };

  if (typeof energy === 'number' && energy < 30)
    return { action: 'rest', reason: 'energy critical', ...base, allowed_actions: ['rest', 'health_actions'] };

  switch (mode) {
    case 'RECOVER':
      return { action: 'rest', reason: 'recovery mode — sleep/health first', ...base };
    case 'CLOSURE': {
      const top = loops[0];
      if (top) return { action: 'close-loop', reason: 'closure mode', target: String(top.convo_id), command: `close ${top.convo_id}`, ...base };
      return { action: 'wait', reason: 'closure mode but no open loops', ...base };
    }
    case 'MAINTENANCE':
      if (!day) return { action: 'plan-day', reason: 'no day plan', command: 'day create A', ...base };
      if (typeof energy === 'number' && energy < 50) return { action: 'rest', reason: 'maintenance + low energy', ...base };
      return { action: 'light-admin', reason: 'maintenance mode', ...base };
    case 'BUILD': {
      if (!day) return { action: 'plan-day', reason: 'build mode needs plan', command: 'day create A', ...base };
      const topFocus = state.focus?.[0]?.name;
      return { action: 'start-work', reason: 'build mode', target: topFocus ?? 'next task', ...base };
    }
    case 'COMPOUND': {
      const topCluster = state.strategic?.top_clusters?.[0]?.label;
      return { action: 'compound', reason: 'compound mode', target: topCluster ?? 'top cluster', ...base };
    }
    case 'SCALE':
      return { action: 'scale', reason: 'scale mode — delegation/infrastructure', ...base };
    default:
      if (!day) return { action: 'plan-day', reason: 'no day plan', ...base };
      return { action: 'wait', reason: 'all gates satisfied', ...base };
  }
}

async function cmdNext() {
  const { data } = await getFullStateRaw();
  respond(decide(data));
}

// ═══════════════════════════════════════════════════════════════
// LAYER 2 — COMPOUNDS
// ═══════════════════════════════════════════════════════════════

async function requestWork(title: string): Promise<{ approved: boolean; job_id?: string; reason?: string }> {
  try {
    const admission = await apiFetch('/api/work/request', { method: 'POST', body: JSON.stringify({ type: 'ai', title, agent: 'atlas-ai' }) });
    if (admission.status === 'DENIED') return { approved: false, reason: admission.reason };
    if (admission.status === 'QUEUED') return { approved: false, reason: admission.reason || 'queued — waiting for capacity' };
    return { approved: true, job_id: admission.job_id };
  } catch { return { approved: true }; } // if work-controller unavailable, proceed anyway
}

async function completeWork(job_id?: string, outcome = 'completed') {
  if (!job_id) return;
  await apiFetch('/api/work/complete', { method: 'POST', body: JSON.stringify({ job_id, outcome }) }).catch(() => {});
}

async function compoundMorning(): Promise<any> {
  const { data: state } = await getFullStateRaw();
  const energy = state.energy?.energy_level ?? 50;
  const dayType: 'A' | 'B' | 'C' = energy > 70 ? 'A' : energy > 40 ? 'B' : 'C';

  const work = await requestWork('morning compound');
  if (!work.approved) return { executed: false, denied: true, reason: work.reason };

  const date = todayDate();
  const cb = await getCycleboardState();
  if (!cb.DayPlans) cb.DayPlans = {};
  let steps = 0;

  // Create day plan if missing
  if (!cb.DayPlans[date]) {
    cb.DayPlans[date] = {
      id: Date.now().toString(36), date, day_type: dayType, time_blocks: [],
      baseline_goal: { text: '', completed: false }, stretch_goal: { text: '', completed: false },
      focus_areas: [], routines_completed: {}, notes: '', rating: 0, progress_snapshots: [], final_progress: 0,
    };
    steps++;
  }
  const plan = cb.DayPlans[date];

  // Populate time blocks from focus areas
  const focusAreas = (state.focus ?? []).slice(0, 3);
  const hours = ['09:00', '10:30', '13:00', '14:30', '16:00'];
  for (let i = 0; i < focusAreas.length && i < hours.length; i++) {
    const name = focusAreas[i].name || focusAreas[i].title || `Focus ${i + 1}`;
    if (!plan.time_blocks.some((b: any) => b.title === name)) {
      plan.time_blocks.push({ id: Date.now().toString(36) + i, time: hours[i], title: name, completed: false });
      steps++;
    }
  }
  plan.time_blocks.sort((a: any, b: any) => (a.time || '').localeCompare(b.time || ''));

  // Set baseline goal from directive
  if (state.directive && !plan.baseline_goal.text) {
    plan.baseline_goal.text = state.directive;
    steps++;
  }

  await updateCycleboardState({ DayPlans: cb.DayPlans });
  await completeWork(work.job_id);

  const decision = decide(state);
  return {
    executed: true, dayType, date, steps,
    briefing: { mode: state.mode, energy, directive: state.directive, open_loops: state.open_loops, top_actions: [decision] },
  };
}

async function compoundCloseStale(args: string[]): Promise<any> {
  const ageDays = parseInt(parseFlag(args, 'age') ?? '7');
  const maxScore = parseInt(parseFlag(args, 'score') ?? '3');

  const { data: state } = await getFullStateRaw();
  const now = Date.now();
  const protectedIds = midLifecycleIds();
  const candidates = (state.loops ?? []).filter((l: any) => {
    const age = l.created_at ? (now - new Date(l.created_at).getTime()) / 86400000 : 999;
    return age > ageDays && (l.score ?? 0) < maxScore;
  });
  const stale = candidates.filter((l: any) => !protectedIds.has(String(l.convo_id)));
  const skippedMidLifecycle = candidates.length - stale.length;
  if (stale.length === 0) return { closed: 0, skipped_mid_lifecycle: skippedMidLifecycle };

  const work = await requestWork(`close-stale (${stale.length} loops)`);
  if (!work.approved) return { executed: false, denied: true, reason: work.reason };

  let closed = 0;
  for (const loop of stale) {
    try {
      await apiFetch('/api/law/close_loop', { method: 'POST', body: JSON.stringify({ loop_id: loop.convo_id, outcome: 'archived', title: 'atlas-ai auto-archive (stale)', status: 'DROPPED', artifact_path: null, coverage_score: null }) });
      closed++;
    } catch (e: any) { debug('close-stale error:', e.message); }
  }

  await completeWork(work.job_id);
  const after = await apiFetch('/api/state/unified').catch(() => null);
  return { closed, skipped_mid_lifecycle: skippedMidLifecycle, new_closure_ratio: after?.derived?.closure_ratio ?? null, new_mode: after?.derived?.mode ?? null };
}

async function compoundDone(args: string[]): Promise<any> {
  const idx = parseInt(args[0]) - 1;
  if (isNaN(idx)) return fail('MISSING_ARG', 'Usage: atlas-ai done <block#>');

  const date = todayDate();
  const cb = await getCycleboardState();
  const plan = cb?.DayPlans?.[date];
  if (!plan || !plan.time_blocks[idx]) return fail('NOT_FOUND', 'Block not found');

  const block = plan.time_blocks[idx];
  block.completed = true;

  // Auto-log win
  if (!cb.MomentumWins) cb.MomentumWins = [];
  cb.MomentumWins.push({ id: Date.now().toString(36), date, timestamp: new Date().toISOString(), description: `Completed: ${block.title}` });

  // Check baseline goal
  const totalBlocks = plan.time_blocks.length;
  const completedBlocks = plan.time_blocks.filter((b: any) => b.completed).length;
  const progressPct = totalBlocks ? Math.round((completedBlocks / totalBlocks) * 100) : 0;
  const baselineMet = progressPct >= 60 && !plan.baseline_goal.completed;
  if (baselineMet) plan.baseline_goal.completed = true;

  await updateCycleboardState({ DayPlans: cb.DayPlans, MomentumWins: cb.MomentumWins });
  return { block: block.title, win_logged: true, baseline_met: baselineMet, progress_pct: progressPct };
}

async function compoundCheckpoint(args: string[]): Promise<any> {
  const energyLevel = parseInt(args[0]);
  if (isNaN(energyLevel)) return fail('MISSING_ARG', 'Usage: atlas-ai checkpoint <energy> [--load N]');
  const load = parseFlag(args, 'load');

  const body: Record<string, any> = { energy_level: energyLevel };
  if (load) body.mental_load = parseInt(load);
  await apiFetch('/api/life-signals/energy', { method: 'POST', body: JSON.stringify(body) });

  const { data: state } = await getFullStateRaw();
  const day = state.day;
  let suggestion: string | null = null;
  if (day) {
    const remaining = (day.time_blocks ?? []).filter((b: any) => !b.completed).length;
    if (energyLevel < 40 && remaining > 2) suggestion = 'Consider rescheduling heavy blocks — energy is low';
  }

  // Emit timeline event
  await apiFetch('/api/timeline', { method: 'POST', body: JSON.stringify({ type: 'CHECKPOINT', source: 'atlas-ai', data: { energy: energyLevel, mode: state.mode } }) }).catch(() => {});

  return { energy: energyLevel, mode: state.mode, suggestion };
}

async function compoundWrap(): Promise<any> {
  const { data: state } = await getFullStateRaw();
  const day = state.day;
  if (!day) return { executed: false, reason: 'no day plan' };

  const totalBlocks = (day.time_blocks ?? []).length;
  const completedBlocks = (day.time_blocks ?? []).filter((b: any) => b.completed).length;
  const rating = totalBlocks ? Math.max(1, Math.round((completedBlocks / totalBlocks) * 5)) : 3;

  const cb = await getCycleboardState();
  const plan = cb.DayPlans?.[todayDate()];
  if (plan) {
    plan.rating = rating;
    const wins = (cb.MomentumWins ?? []).filter((w: any) => w.date === todayDate());
    const reflection = `Day rating: ${rating}/5. Completed ${completedBlocks}/${totalBlocks} blocks. ${wins.length} wins logged.`;
    if (!cb.Journal) cb.Journal = [];
    cb.Journal.push({ id: Date.now().toString(36), date: todayDate(), createdAt: new Date().toISOString(), content: reflection, mood: null });
    await updateCycleboardState({ DayPlans: cb.DayPlans, Journal: cb.Journal });
  }

  // Emit timeline event
  await apiFetch('/api/timeline', { method: 'POST', body: JSON.stringify({ type: 'DAY_WRAP', source: 'atlas-ai', data: { rating, completed: completedBlocks, total: totalBlocks } }) }).catch(() => {});

  return { rating, completed: completedBlocks, total: totalBlocks, reflection_logged: true };
}

async function compoundDo(): Promise<any> {
  const { data: state } = await getFullStateRaw();
  const decision = decide(state);

  if (['wait', 'rest', 'start-work', 'compound', 'scale', 'light-admin'].includes(decision.action))
    return { decision, executed: false };

  const work = await requestWork(`do: ${decision.action}`);
  if (!work.approved) return { decision, executed: false, denied: true, reason: work.reason };

  let result: any = null;
  let outcome = 'completed';
  try {
    if (decision.action === 'close-loop' && decision.target) {
      if (midLifecycleIds().has(String(decision.target))) {
        return { decision, executed: false, skipped_mid_lifecycle: true };
      }
      result = await apiFetch('/api/law/close_loop', { method: 'POST', body: JSON.stringify({ loop_id: decision.target, outcome: 'closed', title: 'atlas-ai auto-close', status: 'RESOLVED', artifact_path: null, coverage_score: null }) });
    } else if (decision.action === 'plan-day') {
      const dayType = (state.energy?.energy_level ?? 50) > 70 ? 'A' : (state.energy?.energy_level ?? 50) > 40 ? 'B' : 'C';
      const date = todayDate(); const cb = await getCycleboardState();
      if (!cb.DayPlans) cb.DayPlans = {};
      if (!cb.DayPlans[date]) {
        cb.DayPlans[date] = { id: Date.now().toString(36), date, day_type: dayType, time_blocks: [], baseline_goal: { text: '', completed: false }, stretch_goal: { text: '', completed: false }, focus_areas: [], routines_completed: {}, notes: '', rating: 0, progress_snapshots: [], final_progress: 0 };
        await updateCycleboardState({ DayPlans: cb.DayPlans });
        result = { created: true, dayType };
      } else { result = { exists: true }; }
    }
  } catch (e: any) { outcome = 'failed'; result = { error: e.message }; }

  await completeWork(work.job_id, outcome);
  return { decision, result, executed: outcome === 'completed', job_id: work.job_id };
}

// ── LLM Compounds ──

async function compoundProcessInbox(): Promise<any> {
  if (!await llmAvailable()) return { skipped: true, reason: 'no llm' };

  const inboxPath = path.join(os.homedir(), 'Desktop', 'inbox.md');
  if (!fs.existsSync(inboxPath)) return { skipped: true, reason: 'no inbox.md' };

  const work = await requestWork('process-inbox');
  if (!work.approved) return { executed: false, denied: true, reason: work.reason };

  const raw = fs.readFileSync(inboxPath, 'utf-8').trim();
  if (!raw) { await completeWork(work.job_id); return { processed: 0 }; }

  const systemPrompt = `You categorize inbox items. For each item, output a JSON array of objects:
{"category":"LOOP|TASK|RESEARCH|REFERENCE|REPLY","title":"short title","detail":"one line summary"}
LOOP = ongoing conversation needing tracking. TASK = actionable to-do. RESEARCH = question needing investigation. REFERENCE = info to file away. REPLY = message/email/thread that needs a response drafted. Return ONLY the JSON array.`;

  const llmResult = await llmGenerate(raw, systemPrompt);
  if (!llmResult) { await completeWork(work.job_id, 'failed'); return { skipped: true, reason: 'llm call failed' }; }

  let items: Array<{ category: string; title: string; detail: string }> = [];
  try { items = JSON.parse(llmResult); } catch {
    const match = llmResult.match(/\[[\s\S]*\]/);
    if (match) try { items = JSON.parse(match[0]); } catch { /* give up */ }
  }
  if (!Array.isArray(items)) items = [];

  ensureDir(USER_ATLAS_DIR);
  const created = { tasks: 0, research: 0, reference: 0, loops: 0, replies: 0 };

  for (const item of items) {
    try {
      switch (item.category) {
        case 'TASK':
        case 'LOOP': {
          const title = item.category === 'LOOP' ? `[LOOP] ${item.title}` : item.title;
          await apiFetch('/api/tasks', { method: 'POST', body: JSON.stringify({ title_template: title, title_params: {}, status: 'OPEN', priority: 'NORMAL', due_at: null, linked_thread: null }) });
          item.category === 'LOOP' ? created.loops++ : created.tasks++;
          break;
        }
        case 'RESEARCH': {
          const entry = JSON.stringify({ id: `rq_${Date.now()}`, query: item.title, context: item.detail, status: 'pending', created: new Date().toISOString() });
          fs.appendFileSync(path.join(USER_ATLAS_DIR, 'research_queue.jsonl'), entry + '\n');
          created.research++;
          break;
        }
        case 'REFERENCE':
          fs.appendFileSync(path.join(USER_ATLAS_DIR, 'reference_log.md'), `\n### ${todayDate()} — ${item.title}\n${item.detail}\n`);
          created.reference++;
          break;
        case 'REPLY': {
          // Auto-populate awaiting_response.json for draft-responses compound
          const awaitQueue = loadAwaitQueue();
          const convoId = item.title.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase().slice(0, 40);
          if (!awaitQueue.some(e => e.convo_id === convoId)) {
            awaitQueue.push({ convo_id: convoId, context: `${item.title}: ${item.detail}` });
            saveAwaitQueue(awaitQueue);
          }
          created.replies++;
          break;
        }
      }
    } catch (e: any) { debug('process-inbox item error:', e.message); }
  }

  const archivePath = path.join(os.homedir(), 'Desktop', `inbox.${todayDate()}.processed.md`);
  fs.renameSync(inboxPath, archivePath);

  await completeWork(work.job_id);
  await apiFetch('/api/timeline', { method: 'POST', body: JSON.stringify({ type: 'INBOX_PROCESSED', source: 'atlas-ai', data: created }) }).catch(() => {});
  return { executed: true, ...created, total: items.length };
}

async function compoundResearchQueue(): Promise<any> {
  if (!await llmAvailable()) return { skipped: true, reason: 'no llm' };

  const queuePath = path.join(USER_ATLAS_DIR, 'research_queue.jsonl');
  if (!fs.existsSync(queuePath)) return { skipped: true, reason: 'no research queue' };

  const lines = fs.readFileSync(queuePath, 'utf-8').trim().split('\n').filter(Boolean);
  const entries = lines.map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
  const pending = entries.filter((e: any) => e.status === 'pending');
  if (pending.length === 0) return { processed: 0, reason: 'no pending entries' };

  const work = await requestWork(`research-queue (${pending.length} items)`);
  if (!work.approved) return { executed: false, denied: true, reason: work.reason };

  const systemPrompt = 'You are a research assistant. Given a question or topic, provide a concise 2-3 paragraph summary with key facts. Be direct and factual. Do not use markdown headers.';
  const digestPath = path.join(USER_ATLAS_DIR, 'research_digest.md');
  let digestSection = `\n## Research Digest — ${todayDate()}\n`;
  let processed = 0, failed = 0;

  for (const entry of pending) {
    const summary = await llmGenerate(`Research topic: ${entry.query}\nContext: ${entry.context || 'none'}`, systemPrompt);
    if (summary) {
      digestSection += `\n### ${entry.title || entry.query}\n${summary}\n`;
      entry.status = 'done';
      entry.completed = new Date().toISOString();
      processed++;
    } else { failed++; }
  }

  fs.appendFileSync(digestPath, digestSection);
  fs.writeFileSync(queuePath, entries.map((e: any) => JSON.stringify(e)).join('\n') + '\n');

  await completeWork(work.job_id);
  await apiFetch('/api/timeline', { method: 'POST', body: JSON.stringify({ type: 'RESEARCH_COMPLETED', source: 'atlas-ai', data: { processed, failed } }) }).catch(() => {});
  return { executed: true, processed, failed };
}

async function compoundDraftResponses(): Promise<any> {
  if (!await llmAvailable()) return { skipped: true, reason: 'no llm' };

  const awaitingPath = path.join(USER_ATLAS_DIR, 'awaiting_response.json');
  if (!fs.existsSync(awaitingPath)) return { skipped: true, reason: 'no awaiting_response.json' };

  let awaiting: Array<{ convo_id: string; context: string; tone?: string }> = [];
  try { awaiting = JSON.parse(fs.readFileSync(awaitingPath, 'utf-8')); } catch { return { skipped: true, reason: 'invalid awaiting_response.json' }; }
  if (!Array.isArray(awaiting) || awaiting.length === 0) return { skipped: true, reason: 'no entries' };

  const work = await requestWork(`draft-responses (${awaiting.length} items)`);
  if (!work.approved) return { executed: false, denied: true, reason: work.reason };

  const draftsDir = path.join(USER_ATLAS_DIR, 'drafts');
  ensureDir(draftsDir);

  const systemPrompt = 'You draft professional, concise responses. The user will provide conversation context. Write a natural reply that addresses the key points. Keep it under 200 words. Do not include greeting/sign-off unless the context suggests formality.';
  let drafted = 0, failed = 0;

  for (const entry of awaiting) {
    const prompt = `Conversation: ${entry.convo_id}\nContext: ${entry.context}${entry.tone ? `\nTone: ${entry.tone}` : ''}`;
    const draft = await llmGenerate(prompt, systemPrompt);
    if (draft) {
      const filename = `${entry.convo_id}_${todayDate()}.md`;
      fs.writeFileSync(path.join(draftsDir, filename), `# Draft Response — ${entry.convo_id}\n\n${draft}\n`);
      drafted++;
    } else { failed++; }
  }

  await completeWork(work.job_id);
  await apiFetch('/api/timeline', { method: 'POST', body: JSON.stringify({ type: 'DRAFTS_GENERATED', source: 'atlas-ai', data: { drafted, failed } }) }).catch(() => {});
  return { executed: true, drafted, failed };
}

// ── Artifact Producers ──

async function compoundStandup(): Promise<any> {
  const { data: state } = await getFullStateRaw();
  const mode = state.mode || 'BUILD';
  const energy = state.energy?.energy_level ?? '?';
  const openLoops = (state.loops ?? []).length;

  // Yesterday's wrap
  const cb = await getCycleboardState();
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  const yesterdayPlan = cb.DayPlans?.[yesterday];
  const yesterdayBlocks = yesterdayPlan?.time_blocks ?? [];
  const completed = yesterdayBlocks.filter((b: any) => b.completed).map((b: any) => b.label || b.task);
  const wins = (cb.MomentumWins ?? []).filter((w: any) => w.date === yesterday).map((w: any) => w.text);

  // Today's plan
  const todayPlan = cb.DayPlans?.[todayDate()];
  const todayBlocks = (todayPlan?.time_blocks ?? []).filter((b: any) => !b.completed).map((b: any) => b.label || b.task);
  const goal = todayPlan?.baseline_goal?.text || 'none set';

  // Blocked
  const staleLoops = (state.loops ?? []).filter((l: any) => {
    const age = l.created_at ? (Date.now() - new Date(l.created_at).getTime()) / 86400000 : 999;
    return age > 7;
  });

  const lines = [
    `# Daily Standup — ${todayDate()}`,
    `**Mode:** ${mode} | **Energy:** ${energy} | **Open loops:** ${openLoops}`,
    '',
    '## Done (yesterday)',
    ...(completed.length ? completed.map((c: string) => `- ${c}`) : ['- (no blocks completed)']),
    ...(wins.length ? ['', '**Wins:**', ...wins.map((w: string) => `- ${w}`)] : []),
    '',
    '## Doing (today)',
    ...(todayBlocks.length ? todayBlocks.map((b: string) => `- ${b}`) : ['- (no plan yet — run `atlas-ai morning`)']),
    `- **Goal:** ${goal}`,
    '',
    '## Blocked',
    ...(staleLoops.length ? staleLoops.slice(0, 5).map((l: any) => `- Loop #${l.convo_id}: ${l.title} (stale)`) : ['- nothing blocking']),
    ...(mode === 'CLOSURE' ? [`- CLOSURE mode active — ${openLoops} loops must close before new work`] : []),
    '',
  ];

  const outputDir = path.join(USER_ATLAS_DIR, 'standups');
  ensureDir(outputDir);
  fs.writeFileSync(path.join(outputDir, `${todayDate()}.md`), lines.join('\n'));
  return { produced: true, file: `standups/${todayDate()}.md` };
}

async function compoundWeeklyBriefing(): Promise<any> {
  const { data: state } = await getFullStateRaw();

  // Read daily snapshots from brain
  const snapshotsRaw = readBrainJson('daily_snapshots.json') ?? [];
  const sevenDaysAgo = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
  const weekSnaps = Array.isArray(snapshotsRaw) ? snapshotsRaw.filter((s: any) => s.date >= sevenDaysAgo) : [];

  // Work history
  let workHistory: any[] = [];
  try {
    const wh = await apiFetch('/api/work/history');
    workHistory = (wh?.completed ?? []).filter((j: any) => {
      const completedAt = j.completed_at ? new Date(j.completed_at).toISOString().slice(0, 10) : '';
      return completedAt >= sevenDaysAgo;
    });
  } catch { /* no work history */ }

  // Timeline events
  let timelineEvents: any[] = [];
  try {
    const tl = await apiFetch('/api/timeline?limit=50');
    timelineEvents = (tl?.events ?? []).slice(0, 20);
  } catch { /* no timeline */ }

  // Momentum wins this week
  const cb = await getCycleboardState();
  const wins = (cb.MomentumWins ?? []).filter((w: any) => w.date >= sevenDaysAgo);

  // Loop closures
  const closureLog = readBrainJson('auto_actor_log.json');
  const autoClosedIds = closureLog?.loops_auto_closed ?? [];

  const weekEnd = todayDate();
  const lines = [
    `# Weekly Briefing — ${sevenDaysAgo} to ${weekEnd}`,
    '',
    '## System State',
    `- **Mode:** ${state.mode || '?'}`,
    `- **Energy:** ${state.energy?.energy_level ?? '?'}`,
    `- **Open loops:** ${(state.loops ?? []).length}`,
    `- **Closure ratio:** ${state.cognitive?.closure_ratio ?? '?'}%`,
    `- **Runway:** ${state.finance?.runway_months ?? '?'} months`,
    '',
    '## Work Completed',
    ...(workHistory.length
      ? workHistory.map((j: any) => `- **${j.title}** (${j.outcome}, ${Math.round((j.duration_ms || 0) / 1000)}s)`)
      : ['- No work completed this week']),
    '',
    '## Wins',
    ...(wins.length ? wins.map((w: any) => `- ${w.text} (${w.date})`) : ['- No wins logged']),
    '',
    '## Loops Closed',
    ...(autoClosedIds.length
      ? autoClosedIds.map((id: string) => `- #${id} (auto-closed)`)
      : ['- No loops closed this week']),
    '',
    '## Mode History',
    ...(weekSnaps.length
      ? weekSnaps.map((s: any) => `- ${s.date}: ${s.mode} (energy=${s.energy_level}, loops=${s.open_loops})`)
      : ['- No daily snapshots available']),
    '',
    '## Key Events',
    ...(() => {
      const meaningful = timelineEvents.filter((e: any) => !['DAEMON_HEARTBEAT', 'heartbeat'].includes(e.type));
      const seen = new Set<string>();
      const deduped = meaningful.filter((e: any) => {
        const key = `${e.type}:${e.data?.title || JSON.stringify(e.data).slice(0, 40)}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
      return deduped.length
        ? deduped.slice(0, 10).map((e: any) => `- ${e.type}: ${e.data?.title || e.data?.action || JSON.stringify(e.data).slice(0, 80)}`)
        : ['- No notable events this week'];
    })(),
    '',
  ];

  const outputDir = path.join(USER_ATLAS_DIR, 'briefings');
  ensureDir(outputDir);
  fs.writeFileSync(path.join(outputDir, `week_${weekEnd}.md`), lines.join('\n'));
  return { produced: true, file: `briefings/week_${weekEnd}.md` };
}

async function compoundIdeaBriefs(): Promise<any> {
  const registryPath = path.join(REPO_ROOT, 'services', 'cognitive-sensor', 'idea_registry.json');
  if (!fs.existsSync(registryPath)) return { skipped: true, reason: 'no idea registry' };

  let registry: any;
  try { registry = JSON.parse(fs.readFileSync(registryPath, 'utf-8')); } catch { return { skipped: true, reason: 'parse error' }; }

  const ideas: any[] = registry.full_registry ?? [];
  if (!ideas.length) return { skipped: true, reason: 'no ideas' };

  // Top 10 by priority_score
  const sorted = [...ideas].sort((a, b) => (b.priority_score ?? 0) - (a.priority_score ?? 0));
  const top = sorted.slice(0, 10);

  const lines = [
    `# Top Ideas Brief — ${todayDate()}`,
    `*${ideas.length} ideas in registry, showing top 10 by priority*`,
    '',
    ...top.flatMap((idea: any, i: number) => [
      `## ${i + 1}. ${idea.canonical_title}`,
      `**Tier:** ${idea.tier} | **Priority:** ${idea.priority_score?.toFixed(1) ?? '?'} | **Mentions:** ${idea.mention_count ?? 0} | **Complexity:** ${idea.complexity ?? '?'}`,
      '',
      idea.canonical_text?.slice(0, 200) + (idea.canonical_text?.length > 200 ? '...' : ''),
      '',
      `**Skills:** ${(idea.skills_required ?? []).join(', ') || 'none listed'}`,
      `**Cluster:** ${idea.vision_cluster ?? 'none'}`,
      ...(idea.related_ideas?.length ? [`**Related:** ${idea.related_ideas.slice(0, 3).join(', ')}`] : []),
      '',
      '---',
      '',
    ]),
  ];

  const outputDir = path.join(USER_ATLAS_DIR, 'briefs');
  ensureDir(outputDir);
  fs.writeFileSync(path.join(outputDir, `top_ideas_${todayDate()}.md`), lines.join('\n'));
  return { produced: true, file: `briefs/top_ideas_${todayDate()}.md`, count: top.length };
}

async function compoundKnowledge(): Promise<any> {
  const evPath = path.join(REPO_ROOT, 'services', 'cognitive-sensor', 'extracted_value.json');
  if (!fs.existsSync(evPath)) return { skipped: true, reason: 'no extracted_value.json' };

  let data: any;
  try { data = JSON.parse(fs.readFileSync(evPath, 'utf-8')); } catch { return { skipped: true, reason: 'parse error' }; }

  const extractions: any[] = data.extractions ?? [];
  if (!extractions.length) return { skipped: true, reason: 'no extractions' };

  // Group by domain/topic
  const byDomain: Record<string, any[]> = {};
  for (const ext of extractions) {
    const rawDomain = ext.classification?.domain;
    const domain = (typeof rawDomain === 'string' && rawDomain !== 'unknown' ? rawDomain : null)
      || ext.strategic_relevance?.highest_priority_idea
      || ext.title
      || 'general';
    if (!byDomain[domain]) byDomain[domain] = [];
    byDomain[domain].push(ext);
  }

  const outputDir = path.join(USER_ATLAS_DIR, 'knowledge');
  ensureDir(outputDir);
  let filesWritten = 0;

  for (const [domain, entries] of Object.entries(byDomain)) {
    const safeName = domain.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase().slice(0, 40);
    const lines = [
      `# Knowledge: ${domain}`,
      `*${entries.length} extracted insights — ${todayDate()}*`,
      '',
      ...entries.flatMap((ext: any) => [
        `## ${ext.title}`,
        `*Source: conversation #${ext.convo_id} | Extracted: ${ext.extracted_at?.slice(0, 10) || '?'}*`,
        '',
        `**Decision:** ${ext.decision} — ${ext.reason}`,
        '',
        `**Topics:** ${(ext.topics ?? []).map((t: any) => t.topic || t).join(', ') || 'none'}`,
        '',
        ...(ext.conversation_summary ? [
          `**Summary:** ${ext.conversation_summary.total_messages ?? '?'} messages, ${ext.conversation_summary.total_words ?? '?'} words`,
        ] : []),
        ...(ext.related_ideas?.length ? [
          `**Related ideas:** ${ext.related_ideas.map((r: any) => r.title || r).join(', ')}`,
        ] : []),
        '',
        '---',
        '',
      ]),
    ];

    fs.writeFileSync(path.join(outputDir, `${safeName}.md`), lines.join('\n'));
    filesWritten++;
  }

  return { produced: true, domains: Object.keys(byDomain), files: filesWritten };
}

async function compoundClosureReports(): Promise<any> {
  const recPath = path.join(REPO_ROOT, 'services', 'cognitive-sensor', 'loop_recommendations.json');
  if (!fs.existsSync(recPath)) return { skipped: true, reason: 'no loop_recommendations.json' };

  let data: any;
  try { data = JSON.parse(fs.readFileSync(recPath, 'utf-8')); } catch { return { skipped: true, reason: 'parse error' }; }

  const autoClosed: any[] = data.auto_closed ?? [];
  const recommendations: any[] = data.recommendations ?? [];
  const all = [...autoClosed, ...recommendations].filter((r: any) => r.recommendation === 'CLOSE' || r.recommendation === 'ARCHIVE');

  if (!all.length) return { skipped: true, reason: 'no closures to report' };

  const outputDir = path.join(USER_ATLAS_DIR, 'closures');
  ensureDir(outputDir);
  let reportsWritten = 0;

  for (const rec of all) {
    const ext = rec.extraction;
    if (!ext) continue;

    const lines = [
      `# Closure Report — ${rec.title}`,
      `*Conversation #${rec.convo_id} | ${rec.recommendation} | Confidence: ${rec.confidence ?? '?'}*`,
      '',
      `**Reason:** ${rec.reason}`,
      `**Outcome:** ${rec.outcome || '?'} | **Trajectory:** ${rec.trajectory || '?'}`,
      '',
      '## Topics',
      ...(ext.topics ?? []).map((t: any) => `- ${t.topic || t} (weight: ${t.weight ?? '?'})`),
      '',
      '## Key Insights',
      `- Messages: ${ext.conversation_summary?.total_messages ?? '?'}`,
      `- Words: ${ext.conversation_summary?.total_words ?? '?'}`,
      ...(ext.strategic_relevance?.connects_to_active_lane ? ['- **Connects to active lane**'] : []),
      '',
      '## Related Ideas',
      ...(ext.related_ideas?.length
        ? ext.related_ideas.map((r: any) => `- ${r.title || r}`)
        : ['- none']),
      '',
      `## Decision`,
      `${rec.recommendation}: ${rec.reason}`,
      '',
    ];

    const safeName = `${rec.convo_id}_${todayDate()}`;
    fs.writeFileSync(path.join(outputDir, `${safeName}.md`), lines.join('\n'));
    reportsWritten++;
  }

  return { produced: true, reports: reportsWritten };
}

// ── Worker: Claim + Execute via Codex ──

async function compoundWork(args: string[]): Promise<any> {
  const dryRun = hasFlag(args, 'dry-run');
  const direct = hasFlag(args, 'direct');

  // 1. Claim next executable task
  let claim: any;
  try {
    claim = await apiFetch('/api/work/claim', { method: 'POST', body: JSON.stringify({ executor_id: 'atlas-ai-worker' }) });
  } catch { return { action: null, reason: 'work queue unreachable' }; }

  const job = claim?.job ?? claim;
  if (!job?.job_id) return { action: null, reason: 'nothing to execute' };

  const { job_id, title, type: jobType, metadata } = job;
  const instructions = metadata?.instructions || metadata?.cmd || title;
  const directiveType = metadata?.directive_type || 'task';
  const taskId = metadata?.task_id || job_id;

  // 2. Get system context for prompt
  let stateCtx = '';
  try {
    const { data } = await getFullStateRaw();
    const mode = data.mode || 'BUILD';
    const energy = data.energy?.energy_level ?? '?';
    const lanes = data.directive?.focus_areas?.join(', ') || 'none';
    stateCtx = `System: ${mode} mode, energy=${energy}, lanes: ${lanes}`;
  } catch { stateCtx = 'System state unavailable'; }

  // 3. Build prompt
  const outputDir = path.join(USER_ATLAS_DIR, 'worker_output');
  ensureDir(outputDir);
  const outputFile = `${taskId}_${todayDate()}.md`;

  const prompt = [
    stateCtx,
    `Task: ${title}`,
    `Type: ${directiveType}`,
    `Instructions: ${instructions}`,
    '',
    'You are executing a task for the Atlas governance system.',
    'Produce a concrete output:',
    '- A file written to the codebase, or',
    '- A document/analysis, or',
    '- A structured result',
    '',
    `Work in: ${REPO_ROOT}`,
    `Save primary output to: ${path.join(outputDir, outputFile)}`,
    'Be specific. Produce the actual work product, not a plan.',
  ].join('\n');

  if (dryRun) {
    return { dry_run: true, job_id, title, directive_type: directiveType, prompt };
  }

  if (direct) {
    // Direct mode: return prompt for Claude to handle
    return { direct: true, job_id, title, prompt, instructions: 'Execute this prompt manually via Claude' };
  }

  // 4. Execute via Codex
  const escapedPrompt = prompt.replace(/"/g, '\\"').replace(/\n/g, '\\n');
  let output = '';
  let outcome = 'completed';
  const t0 = performance.now();

  try {
    // Heartbeat before long execution
    await apiFetch('/api/work/heartbeat', { method: 'POST', body: JSON.stringify({ job_id, executor_id: 'atlas-ai-worker' }) }).catch(() => {});

    output = execSync(
      `codex exec --dangerously-bypass-approvals-and-sandbox -C "${REPO_ROOT}" "${escapedPrompt}"`,
      { timeout: 120000, encoding: 'utf-8', maxBuffer: 1024 * 1024 },
    ).trim();

    // Cap output
    if (output.length > 5000) output = output.slice(0, 5000) + '\n[...truncated]';

    // Save output
    fs.writeFileSync(path.join(outputDir, outputFile), `# Worker Output — ${title}\n\n${output}\n`);
  } catch (e: any) {
    outcome = 'failed';
    output = e.message?.slice(0, 2000) || 'execution failed';
  }

  const durationMs = Math.round(performance.now() - t0);

  // 5. Report completion
  await apiFetch('/api/work/complete', {
    method: 'POST',
    body: JSON.stringify({ job_id, outcome, result: { output: output.slice(0, 1000) }, metrics: { duration_ms: durationMs } }),
  }).catch(() => {});

  await apiFetch('/api/timeline', {
    method: 'POST',
    body: JSON.stringify({ type: 'WORK_EXECUTED', source: 'atlas-ai-worker', data: { job_id, title, outcome, duration_ms: durationMs } }),
  }).catch(() => {});

  return { executed: true, job_id, title, outcome, duration_ms: durationMs, output_file: outputFile };
}

// ═══════════════════════════════════════════════════════════════
// LAYER 3 — AGENT LOOP
// ═══════════════════════════════════════════════════════════════

interface AgentState { date: string; ranToday: Record<string, string>; lastEnergy: number | null; lastMode: string | null; }

function loadAgentState(): AgentState {
  const stateFile = path.join(ATLAS_DIR, 'agent_state.json');
  try {
    const s = JSON.parse(fs.readFileSync(stateFile, 'utf-8'));
    if (s.date !== todayDate()) return { date: todayDate(), ranToday: {}, lastEnergy: null, lastMode: null };
    return s;
  } catch { return { date: todayDate(), ranToday: {}, lastEnergy: null, lastMode: null }; }
}

function saveAgentState(state: AgentState) {
  ensureDir(ATLAS_DIR);
  fs.writeFileSync(path.join(ATLAS_DIR, 'agent_state.json'), JSON.stringify(state, null, 2));
}

function loadConfig(): any {
  const configFile = path.join(ATLAS_DIR, 'agent_config.json');
  try { return JSON.parse(fs.readFileSync(configFile, 'utf-8')); }
  catch {
    return { version: 1, actions: { morning: { enabled: true }, close_stale: { enabled: true, age_days: 7, max_score: 3 }, wrap: { enabled: true } } };
  }
}

function rotateLogIfNeeded(logPath: string, maxSizeMB = 10, maxFiles = 5): void {
  try {
    if (!fs.existsSync(logPath)) return;
    const stats = fs.statSync(logPath);
    if (stats.size < maxSizeMB * 1024 * 1024) return;
    for (let i = maxFiles; i >= 1; i--) {
      const src = i === 1 ? logPath : `${logPath}.${i - 1}`;
      const dst = `${logPath}.${i}`;
      if (i === maxFiles && fs.existsSync(dst)) fs.unlinkSync(dst);
      if (fs.existsSync(src)) fs.renameSync(src, dst);
    }
  } catch { /* rotation errors are non-fatal */ }
}

function agentLog(action: string, result: any, ms: number) {
  ensureDir(ATLAS_DIR);
  const logPath = path.join(ATLAS_DIR, 'agent.log');
  rotateLogIfNeeded(logPath);
  const entry = JSON.stringify({ ts: new Date().toISOString(), action, result: { ok: !result?.error }, ms }) + '\n';
  fs.appendFileSync(logPath, entry);
}

function pickAction(state: Record<string, any>, hour: number, config: any, agentState: AgentState): string | null {
  const hasDay = !!state.day;
  const staleLoops = (state.loops ?? []).filter((l: any) => {
    const age = l.created_at ? (Date.now() - new Date(l.created_at).getTime()) / 86400000 : 999;
    return age > (config.actions?.close_stale?.age_days ?? 7) && (l.score ?? 0) < (config.actions?.close_stale?.max_score ?? 3);
  });

  if (hour >= 6 && hour <= 10 && !hasDay && !agentState.ranToday.morning && config.actions?.morning?.enabled !== false) return 'morning';
  if (staleLoops.length >= 3 && !agentState.ranToday['close-stale'] && config.actions?.close_stale?.enabled !== false) return 'close-stale';
  if (hour >= 20 && hour <= 23 && hasDay && !state.day.rating && !agentState.ranToday.wrap && config.actions?.wrap?.enabled !== false) return 'wrap';

  // Worker: execute queued tasks via Codex (can run multiple times per day)
  if (state.work?.queued_count > 0 || state.work?.active_count > 0) return 'work';

  // Artifact producers (no LLM needed)
  if (hour >= 6 && hour <= 10 && !agentState.ranToday.standup) return 'standup';
  if (new Date().getDay() === 0 && !agentState.ranToday.weekly) return 'weekly';  // Sundays
  if (!agentState.ranToday['idea-briefs']) return 'idea-briefs';
  if (!agentState.ranToday.knowledge) return 'knowledge';
  if (!agentState.ranToday['closure-reports']) return 'closure-reports';

  // LLM compounds (only if endpoint configured)
  if (LLM_ENDPOINT) {
    if (hour >= 7 && hour <= 11 && !agentState.ranToday['process-inbox'] && fs.existsSync(path.join(os.homedir(), 'Desktop', 'inbox.md')))
      return 'process-inbox';
    if (hour >= 11 && hour <= 15 && !agentState.ranToday['research-queue']) {
      const qp = path.join(USER_ATLAS_DIR, 'research_queue.jsonl');
      if (fs.existsSync(qp) && fs.readFileSync(qp, 'utf-8').includes('"pending"')) return 'research-queue';
    }
    if (hour >= 15 && hour <= 20 && !agentState.ranToday['draft-responses'] && fs.existsSync(path.join(USER_ATLAS_DIR, 'awaiting_response.json')))
      return 'draft-responses';
  }

  return null;
}

async function runAction(action: string, state: Record<string, any>, config: any, dryRun: boolean): Promise<any> {
  if (dryRun) { console.error(`[dry-run] would run: ${action}`); return { dry_run: true, action }; }
  const t0 = performance.now();
  let result: any;
  switch (action) {
    case 'morning': result = await compoundMorning(); break;
    case 'close-stale': result = await compoundCloseStale(['--age', String(config.actions?.close_stale?.age_days ?? 7), '--score', String(config.actions?.close_stale?.max_score ?? 3)]); break;
    case 'wrap': result = await compoundWrap(); break;
    case 'process-inbox': result = await compoundProcessInbox(); break;
    case 'research-queue': result = await compoundResearchQueue(); break;
    case 'draft-responses': result = await compoundDraftResponses(); break;
    case 'work': result = await compoundWork(['--once']); break;
    case 'standup': result = await compoundStandup(); break;
    case 'weekly': result = await compoundWeeklyBriefing(); break;
    case 'idea-briefs': result = await compoundIdeaBriefs(); break;
    case 'knowledge': result = await compoundKnowledge(); break;
    case 'closure-reports': result = await compoundClosureReports(); break;
    default: result = { unknown: action };
  }
  agentLog(action, result, Math.round(performance.now() - t0));
  return result;
}

async function cmdAgent(args: string[]) {
  const once = hasFlag(args, 'once');
  const daemon = hasFlag(args, 'daemon');
  const dryRun = hasFlag(args, 'dry-run');
  const interval = parseInt(parseFlag(args, 'interval') ?? '60') * 1000;
  const configPath = parseFlag(args, 'config');
  const config = configPath ? JSON.parse(fs.readFileSync(configPath, 'utf-8')) : loadConfig();
  const agentState = loadAgentState();

  const tick = async () => {
    try {
      const { data: state } = await getFullStateRaw();
      const hour = new Date().getHours();
      const action = pickAction(state, hour, config, agentState);
      if (action) {
        debug(`agent: running ${action}`);
        const result = await runAction(action, state, config, dryRun);
        if (!dryRun) {
          agentState.ranToday[action] = new Date().toISOString();
          agentState.lastEnergy = state.energy?.energy_level ?? null;
          agentState.lastMode = state.mode ?? null;
          saveAgentState(agentState);
        }
        return result;
      }
      debug('agent: nothing to do');
      return null;
    } catch (e: any) { debug('agent tick error:', e.message); return null; }
  };

  if (once || (!daemon && !once)) {
    const result = await tick();
    respond(result ?? { action: null, reason: 'nothing to do' });
    return;
  }

  // Daemon mode — keep running
  debug(`agent daemon started (interval=${interval}ms, dry-run=${dryRun})`);
  await tick();
  setInterval(tick, interval);
}

// ═══════════════════════════════════════════════════════════════
// META & DISPATCHER
// ═══════════════════════════════════════════════════════════════

function cmdCapabilities() {
  respond({
    version: '1.0',
    layers: ['primitives', 'compounds', 'agent'],
    commands: {
      read: ['state', 'loops', 'day', 'cognitive', 'directive', 'health', 'osint', 'energy', 'finance', 'skills', 'network', 'next', 'capabilities', 'help'],
      write: ['close', 'archive', 'energy', 'finance', 'skills', 'network', 'day create|block|done|goal|rate', 'task add|done', 'win', 'journal add', 'refresh', 'await list|add|remove|clear'],
      compound: ['morning', 'close-stale', 'done', 'checkpoint', 'wrap', 'do', 'process-inbox', 'research-queue', 'draft-responses', 'work', 'standup', 'weekly', 'idea-briefs', 'knowledge', 'closure-reports'],
      agent: ['agent --once', 'agent --daemon', 'agent --dry-run'],
    },
    modes: Object.keys(MODE_ALLOWED_ACTIONS),
    mode_actions: MODE_ALLOWED_ACTIONS,
  });
}

function cmdHelp() {
  respond({
    usage: 'atlas-ai <command> [args]',
    commands: {
      'state [--fields x,y]': 'Full system snapshot',
      'next': 'Recommended action based on mode/energy',
      'do': 'Decide + execute with work admission',
      'morning': 'Start-of-day compound (plan + blocks + goal)',
      'close-stale [--age N] [--score N]': 'Batch archive stale loops',
      'done <block#>': 'Complete block + log win + check goals',
      'checkpoint <energy> [--load N]': 'Mid-day state update',
      'wrap': 'End-of-day compound (rate + reflect + journal)',
      'close <id>': 'Close a loop',
      'archive <id>': 'Archive a loop',
      'energy [N] [--load N] [--sleep N]': 'Read or update energy',
      'finance [--runway N] [--income N]': 'Read or update finance',
      'skills [--util N] [--learning]': 'Read or update skills',
      'network [--collab N]': 'Read or update network',
      'day [date|create|block|done|goal|rate]': 'Day plan management',
      'task [add|done] <arg>': 'Task management',
      'win <text>': 'Log a momentum win',
      'journal [add] <text>': 'Journal management',
      'await [list|add|remove|clear]': 'Manage awaiting_response queue for draft-responses',
      'refresh': 'Run cognitive pipeline',
      'loops': 'List open loops',
      'cognitive': 'Cognitive state (drift, compliance)',
      'directive': 'Strategic directive + clusters',
      'health': 'Service health check',
      'osint': 'OSINT feed',
      'capabilities': 'Machine-readable command schema',
      'process-inbox': 'LLM-categorize ~/Desktop/inbox.md → tasks/loops/research/reference',
      'research-queue': 'LLM-summarize pending research items → digest',
      'draft-responses': 'LLM-draft replies for awaiting conversations',
      'work [--dry-run|--direct]': 'Claim + execute next task via Codex',
      'standup': 'Produce daily standup markdown (did/doing/blocked)',
      'weekly': 'Produce weekly briefing markdown',
      'idea-briefs': 'Produce top 10 ideas brief from registry',
      'knowledge': 'Extract knowledge entries from closed loop value',
      'closure-reports': 'Produce closure reports for archived loops',
      'agent [--once|--daemon] [--dry-run]': 'Agent loop',
      'help': 'This help',
    },
  });
}

async function main() {
  const args = process.argv.slice(2);
  const cmd = args[0] || 'state';
  const rest = args.slice(1);

  try {
    switch (cmd) {
      case 'state': return cmdState(rest);
      case 'next': return cmdNext();
      case 'do': return respond(await compoundDo());
      case 'morning': return respond(await compoundMorning());
      case 'close-stale': return respond(await compoundCloseStale(rest));
      case 'done': return respond(await compoundDone(rest));
      case 'checkpoint': return respond(await compoundCheckpoint(rest));
      case 'wrap': return respond(await compoundWrap());
      case 'process-inbox': return respond(await compoundProcessInbox());
      case 'research-queue': return respond(await compoundResearchQueue());
      case 'draft-responses': return respond(await compoundDraftResponses());
      case 'work': return respond(await compoundWork(rest));
      case 'standup': return respond(await compoundStandup());
      case 'weekly': return respond(await compoundWeeklyBriefing());
      case 'idea-briefs': return respond(await compoundIdeaBriefs());
      case 'knowledge': return respond(await compoundKnowledge());
      case 'closure-reports': return respond(await compoundClosureReports());
      case 'close': return cmdClose(rest);
      case 'archive': return cmdArchive(rest);
      case 'energy': return cmdEnergy(rest);
      case 'finance': return cmdFinance(rest);
      case 'skills': return cmdSkills(rest);
      case 'network': return cmdNetwork(rest);
      case 'day': return cmdDay(rest);
      case 'task': return cmdTask(rest);
      case 'win': return cmdWin(rest);
      case 'journal': return cmdJournal(rest);
      case 'await': return cmdAwait(rest);
      case 'refresh': return cmdRefresh();
      case 'loops': return cmdLoops();
      case 'cognitive': return cmdCognitive();
      case 'directive': return cmdDirective();
      case 'health': return cmdHealth();
      case 'osint': return cmdOsint();
      case 'capabilities': return cmdCapabilities();
      case 'help': return cmdHelp();
      case 'agent': return cmdAgent(rest);
      default: fail('UNKNOWN_COMMAND', `Unknown: ${cmd}. Run: atlas-ai help`);
    }
  } catch (e: any) { fail('FATAL', e.message); }
}

main();
