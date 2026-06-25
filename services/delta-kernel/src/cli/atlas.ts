#!/usr/bin/env tsx
/**
 * Atlas CLI — Unified command interface for the Pre Atlas system.
 * Every command calls delta-kernel API and formats for terminal.
 * No external dependencies beyond Node built-ins.
 */

import { execSync, exec as execCb } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const API = 'http://localhost:3001';
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..', '..');

// ── Auth ──

let cachedToken: string | null = null;

async function getToken(): Promise<string | null> {
  if (cachedToken) return cachedToken;
  try {
    const res = await fetch(`${API}/api/auth/token`);
    const json = await res.json() as any;
    cachedToken = json.token ?? null;
    return cachedToken;
  } catch {
    return null;
  }
}

async function apiFetch(urlPath: string, options: RequestInit = {}): Promise<any> {
  const token = await getToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (options.body) headers['Content-Type'] = 'application/json';
  const res = await fetch(`${API}${urlPath}`, { ...options, headers });
  return res.json();
}

// ── ANSI helpers ──

const bold = (s: string) => `\x1b[1m${s}\x1b[0m`;
const dim = (s: string) => `\x1b[2m${s}\x1b[0m`;
const green = (s: string) => `\x1b[32m${s}\x1b[0m`;
const red = (s: string) => `\x1b[31m${s}\x1b[0m`;
const yellow = (s: string) => `\x1b[33m${s}\x1b[0m`;
const cyan = (s: string) => `\x1b[36m${s}\x1b[0m`;
const magenta = (s: string) => `\x1b[35m${s}\x1b[0m`;
const dot = (up: boolean) => up ? green('●') : red('●');

function box(title: string, lines: string[]) {
  const w = 52;
  const bar = '─'.repeat(w);
  console.log(`╔═${bold(title.padEnd(w))}═╗`);
  for (const line of lines) {
    if (line === '---') {
      console.log(`╟─${bar}─╢`);
    } else {
      console.log(`║ ${line.padEnd(w)} ║`);
    }
  }
  console.log(`╚═${'═'.repeat(w)}═╝`);
}

// ── Brain file helpers ──

const BRAIN_DIR = path.resolve(REPO_ROOT, 'services', 'cognitive-sensor', 'cycleboard', 'brain');

function readBrainJson(file: string): any {
  try { return JSON.parse(fs.readFileSync(path.join(BRAIN_DIR, file), 'utf-8')); }
  catch { return null; }
}

function readBrainText(file: string): string | null {
  try { return fs.readFileSync(path.join(BRAIN_DIR, file), 'utf-8').trim(); }
  catch { return null; }
}

function progressBar(pct: number, width = 20): string {
  const filled = Math.round((pct / 100) * width);
  const empty = width - filled;
  const color = pct >= 70 ? green : pct >= 50 ? yellow : dim;
  return color('█'.repeat(filled) + '░'.repeat(empty)) + ` ${pct}%`;
}

function normalizePct(val: number | null | undefined): string {
  if (val == null) return '--';
  return val > 1 ? val.toFixed(1) + '%' : (val * 100).toFixed(1) + '%';
}

function modeColor(mode: string): string {
  switch (mode) {
    case 'CLOSURE': case 'RECOVER': return red(mode);
    case 'MAINTENANCE': return yellow(mode);
    case 'BUILD': return green(mode);
    case 'COMPOUND': return magenta(mode);
    case 'SCALE': return cyan(mode);
    default: return mode;
  }
}

function ageText(ts: string | null | undefined): string {
  if (!ts) return '--';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ── Flag parsing ──

function parseFlag(args: string[], flag: string): string | undefined {
  const idx = args.indexOf('--' + flag);
  return idx >= 0 && idx + 1 < args.length ? args[idx + 1] : undefined;
}

function hasFlag(args: string[], flag: string): boolean {
  return args.includes('--' + flag);
}

// ── Commands ──

async function showStatus() {
  const [unified, health, signals] = await Promise.all([
    apiFetch('/api/state/unified').catch(() => null),
    apiFetch('/api/services/health').catch(() => null),
    apiFetch('/api/life-signals').catch(() => null),
  ]);

  const mode = unified?.derived?.mode || '--';
  const directive = unified?.derived?.primary_order || unified?.cognitive?.today?.directive || '--';
  const openLoops = unified?.derived?.open_loops ?? '--';
  const closureRatio = unified?.derived?.closure_ratio != null ? (unified.derived.closure_ratio * 100).toFixed(1) + '%' : '--';
  const streak = unified?.derived?.streak_days ?? '--';
  const closuresToday = unified?.derived?.closures_today ?? 0;
  const topLoop = unified?.cognitive?.cognitive_state?.loops?.[0]?.title || '--';
  const energy = signals?.energy?.energy_level ?? '--';
  const load = signals?.energy?.mental_load ?? '--';
  const sleep = signals?.energy?.sleep_quality ?? '--';
  const lastRefresh = signals?.generated_at ? new Date(signals.generated_at).toLocaleString() : '--';

  const deltaUp = health?.delta?.status === 'up';
  const uascUp = health?.uasc?.status === 'up';
  const cortexUp = health?.cortex?.status === 'up';

  box('ATLAS STATUS', [
    `${bold('Mode:')} ${cyan(mode)}`,
    `${bold('Directive:')} ${directive}`,
    '---',
    `Services: ${dot(deltaUp)} Delta  ${dot(uascUp)} UASC  ${dot(cortexUp)} Cortex`,
    `Pipeline: ${dim('Last refresh')} ${lastRefresh}`,
    `Energy: ${energy}  Load: ${load}/10  Sleep: ${sleep}/5`,
    '---',
    `Open Loops: ${openLoops}  Closure Ratio: ${closureRatio}`,
    `Streak: ${streak} day(s)  Closures Today: ${closuresToday}`,
    '---',
    `Top Loop: ${topLoop}`,
  ]);
}

async function showMode() {
  const data = await apiFetch('/api/state/unified');
  const mode = data?.derived?.mode || '--';
  const buildAllowed = data?.derived?.build_allowed ?? false;
  const reason = data?.cognitive?.today?.reason || data?.derived?.primary_order || '--';
  console.log(`${bold('Mode:')} ${cyan(mode)}`);
  console.log(`${bold('Build Allowed:')} ${buildAllowed ? green('YES') : red('NO')}`);
  console.log(`${bold('Reason:')} ${reason}`);
}

async function showHealth() {
  const data = await apiFetch('/api/services/health');
  if (!data) { console.log(red('Could not reach delta-kernel')); return; }
  for (const [name, info] of Object.entries(data) as [string, any][]) {
    console.log(`  ${dot(info.status === 'up')} ${bold(name.padEnd(10))} ${info.status === 'up' ? green('UP') : red('DOWN')}`);
  }
}

async function getSignals(): Promise<any> {
  return apiFetch('/api/life-signals').catch(() => {
    // Fallback to brain files
    return {
      energy: readBrainJson('energy_metrics.json'),
      finance: readBrainJson('finance_metrics.json'),
      skills: readBrainJson('skills_metrics.json'),
      network: readBrainJson('network_metrics.json'),
    };
  });
}

async function showEnergy() {
  const signals = await getSignals();
  const e = signals?.energy;
  if (!e) { console.log(dim('No energy data. Run: atlas refresh')); return; }
  const level = e.energy_level ?? '--';
  const load = e.mental_load ?? '--';
  const sleepQ = e.sleep_quality ?? '--';
  const rawBurnout = e.burnout_risk;
  const burnout = typeof rawBurnout === 'string' ? rawBurnout
    : rawBurnout === true ? 'HIGH'
    : rawBurnout === false ? 'LOW'
    : (typeof level === 'number' ? (level < 30 ? 'HIGH' : level < 50 ? 'MEDIUM' : 'LOW') : 'LOW');
  const phase = e.life_phase ?? '--';
  const alert = e.red_alert_active ? red(' RED ALERT') : '';
  box('ENERGY' + alert, [
    `${bold('Level:')}       ${level}/100    ${typeof level === 'number' ? progressBar(level) : '--'}`,
    `${bold('Mental Load:')} ${load}/10`,
    `${bold('Sleep:')}       ${sleepQ}/5     ${'★'.repeat(Math.min(sleepQ || 0, 5))}${'☆'.repeat(Math.max(0, 5 - (sleepQ || 0)))}`,
    `${bold('Burnout:')}     ${burnout === 'HIGH' ? red(burnout) : burnout === 'MEDIUM' ? yellow(burnout) : green(String(burnout))}`,
    `${bold('Life Phase:')}  ${phase}`,
  ]);
}

async function energyCmd(args: string[]) {
  if (args.length === 0) return showEnergy();
  const body: Record<string, any> = {};
  if (args[0] && !args[0].startsWith('--')) body.energy_level = parseInt(args[0]);
  const load = parseFlag(args, 'load');
  if (load) body.mental_load = parseInt(load);
  const sleep = parseFlag(args, 'sleep');
  if (sleep) body.sleep_quality = parseInt(sleep);
  const data = await apiFetch('/api/life-signals/energy', { method: 'POST', body: JSON.stringify(body) });
  console.log(green('Energy updated:'), `level=${data.energy?.energy_level} load=${data.energy?.mental_load} sleep=${data.energy?.sleep_quality}`);
}

async function showFinance() {
  const signals = await getSignals();
  const f = signals?.finance;
  if (!f) { console.log(dim('No finance data. Run: atlas refresh')); return; }
  const runway = f.runway_months ?? '--';
  const income = f.monthly_income ?? '--';
  const expenses = f.monthly_expenses ?? '--';
  const delta = f.money_delta ?? (typeof income === 'number' && typeof expenses === 'number' ? income - expenses : '--');
  const runwayColor = typeof runway === 'number' ? (runway < 2 ? red : runway < 6 ? yellow : green) : dim;
  const deltaColor = typeof delta === 'number' ? (delta >= 0 ? green : red) : dim;
  box('FINANCE', [
    `${bold('Runway:')}     ${runwayColor(runway + ' months')}`,
    `${bold('Income:')}     $${income}`,
    `${bold('Expenses:')}   $${expenses}`,
    `${bold('Net Delta:')}  ${deltaColor((typeof delta === 'number' && delta >= 0 ? '+' : '') + '$' + delta)}`,
  ]);
}

async function financeCmd(args: string[]) {
  if (args.length === 0) return showFinance();
  const body: Record<string, any> = {};
  const runway = parseFlag(args, 'runway');
  if (runway) body.runway_months = parseFloat(runway);
  const income = parseFlag(args, 'income');
  if (income) body.monthly_income = parseFloat(income);
  const expenses = parseFlag(args, 'expenses');
  if (expenses) body.monthly_expenses = parseFloat(expenses);
  const data = await apiFetch('/api/life-signals/finance', { method: 'POST', body: JSON.stringify(body) });
  console.log(green('Finance updated:'), `runway=${data.finance?.runway_months}mo income=${data.finance?.monthly_income} expenses=${data.finance?.monthly_expenses} delta=${data.finance?.money_delta}`);
}

async function showSkills() {
  const signals = await getSignals();
  const s = signals?.skills;
  if (!s) { console.log(dim('No skills data. Run: atlas refresh')); return; }
  const util = s.utilization_pct ?? '--';
  const learning = s.active_learning ?? false;
  const mastery = s.mastery_count ?? '--';
  const growth = s.growth_count ?? '--';
  box('SKILLS', [
    `${bold('Utilization:')}    ${typeof util === 'number' ? progressBar(util) : '--'}`,
    `${bold('Active Learning:')} ${learning ? green('YES') : dim('NO')}`,
    `${bold('Mastered:')}       ${mastery}`,
    `${bold('Growing:')}        ${growth}`,
  ]);
}

async function skillsCmd(args: string[]) {
  if (args.length === 0) return showSkills();
  const body: Record<string, any> = {};
  const util = parseFlag(args, 'util');
  if (util) body.utilization_pct = parseFloat(util);
  if (hasFlag(args, 'learning')) body.active_learning = true;
  const mastery = parseFlag(args, 'mastery');
  if (mastery) body.mastery_count = parseInt(mastery);
  const growth = parseFlag(args, 'growth');
  if (growth) body.growth_count = parseInt(growth);
  const data = await apiFetch('/api/life-signals/skills', { method: 'POST', body: JSON.stringify(body) });
  console.log(green('Skills updated:'), `util=${data.skills?.utilization_pct}% learning=${data.skills?.active_learning}`);
}

async function showNetwork() {
  const signals = await getSignals();
  const n = signals?.network;
  if (!n) { console.log(dim('No network data. Run: atlas refresh')); return; }
  const collab = n.collaboration_score ?? '--';
  const rels = n.active_relationships ?? '--';
  const outreach = n.outreach_this_week ?? '--';
  const warning = typeof collab === 'number' && collab < 20 ? red(' ISOLATION WARNING') : '';
  box('NETWORK' + warning, [
    `${bold('Collaboration:')}  ${collab}/100`,
    `${bold('Relationships:')}  ${rels} active`,
    `${bold('Outreach:')}       ${outreach} this week`,
  ]);
}

async function networkCmd(args: string[]) {
  if (args.length === 0) return showNetwork();
  const body: Record<string, any> = {};
  const collab = parseFlag(args, 'collab');
  if (collab) body.collaboration_score = parseInt(collab);
  const rels = parseFlag(args, 'relationships');
  if (rels) body.active_relationships = parseInt(rels);
  const outreach = parseFlag(args, 'outreach');
  if (outreach) body.outreach_this_week = parseInt(outreach);
  const data = await apiFetch('/api/life-signals/network', { method: 'POST', body: JSON.stringify(body) });
  console.log(green('Network updated:'), `collab=${data.network?.collaboration_score} relationships=${data.network?.active_relationships}`);
}

async function showLoops() {
  const data = await apiFetch('/api/state/unified');
  const loops = data?.cognitive?.cognitive_state?.loops || [];
  if (loops.length === 0) { console.log('No open loops.'); return; }
  console.log(bold('Open Loops:'));
  for (const loop of loops.slice(0, 10)) {
    const status = loop.status ? ` ${yellow('[' + loop.status + ']')}` : '';
    const artifact = loop.artifact_path ? ` ${dim('-> ' + loop.artifact_path)}` : '';
    console.log(`  ${dim(String(loop.convo_id).padEnd(6))} ${loop.title?.padEnd(40) || 'Untitled'} ${yellow('score=' + loop.score)}${status}${artifact}`);
  }
}

async function showLifecycle() {
  const boardPath = path.resolve(REPO_ROOT, 'services', 'cognitive-sensor', 'cycleboard', 'brain', 'lifecycle_board.json');
  let board: any;
  try { board = JSON.parse(fs.readFileSync(boardPath, 'utf-8')); }
  catch {
    console.log(red('No lifecycle_board.json. Run: python wire_cycleboard.py'));
    return;
  }
  const inProgress: any[] = board.in_progress ?? [];
  const terminal = board.terminal_today ?? { DONE: [], RESOLVED: [], DROPPED: [] };
  const counts = board.counts ?? {};

  console.log(bold('LIFECYCLE') + '  ' + dim(`(generated ${board.generated_at ?? '?'})`));
  console.log('');
  console.log(bold('In progress'));
  if (inProgress.length === 0) { console.log(`  ${dim('(none)')}`); }
  else for (const t of inProgress) {
    const tag = `[${yellow(t.status)}]`;
    const id = String(t.convo_id ?? '?').padEnd(6);
    const title = (t.title ?? 'untitled').slice(0, 50);
    console.log(`  ${tag.padEnd(20)} ${cyan(id)} ${title}`);
    if (t.artifact_path) console.log(`  ${' '.repeat(20)} ${dim('-> ' + t.artifact_path)}`);
  }

  console.log('');
  console.log(bold('Finished today'));
  let anyTerminal = false;
  for (const status of ['DONE', 'RESOLVED', 'DROPPED']) {
    for (const c of terminal[status] ?? []) {
      anyTerminal = true;
      const color = status === 'DONE' ? green : status === 'RESOLVED' ? cyan : dim;
      const tag = `[${color(status)}]`;
      const id = String(c.loop_id ?? '?').padEnd(6);
      const title = (c.title ?? 'untitled').slice(0, 40);
      const cov = c.coverage_score != null ? ` ${dim('cov=' + Number(c.coverage_score).toFixed(2))}` : '';
      const art = c.artifact_path ? ` ${dim('-> ' + c.artifact_path)}` : '';
      console.log(`  ${tag.padEnd(20)} ${id} ${title}${cov}${art}`);
    }
  }
  if (!anyTerminal) console.log(`  ${dim('(none)')}`);

  console.log('');
  const fmt = (k: string) => `${k}:${counts[k] ?? 0}`;
  console.log(bold('Counts') + '  ' + ['HARVESTED','PLANNED','BUILDING','REVIEWING'].map(fmt).join(' ') + '  ' + dim('/') + '  ' + ['DONE','RESOLVED','DROPPED'].map(fmt).join(' '));
}

async function closeLoop(args: string[], outcome: string) {
  const loopId = args[0];
  if (!loopId) { console.log(red('Usage: atlas close <loop_id>')); return; }
  const status = outcome === 'archived' ? 'DROPPED' : 'RESOLVED';
  const data = await apiFetch('/api/law/close_loop', {
    method: 'POST',
    body: JSON.stringify({ loop_id: loopId, outcome, title: `CLI ${outcome}`, status, artifact_path: null, coverage_score: null }),
  });
  if (data?.success) {
    console.log(green(`Loop ${loopId} ${outcome}. Mode: ${data.mode}`));
  } else {
    console.log(yellow(`Response: ${JSON.stringify(data)}`));
  }
}

async function showTasks() {
  const data = await apiFetch('/api/tasks');
  const tasks = Array.isArray(data) ? data : data?.tasks || [];
  if (tasks.length === 0) { console.log('No tasks.'); return; }
  console.log(bold('Tasks:'));
  for (const t of tasks.slice(0, 15)) {
    const id = (t.entity_id || t.id || '--').slice(0, 8);
    const title = t.title_template || t.title || 'Untitled';
    const status = t.status || '--';
    console.log(`  ${dim(id)} ${title.padEnd(35)} ${status === 'DONE' ? green(status) : status === 'IN_PROGRESS' ? yellow(status) : status}`);
  }
}

async function addTask(args: string[]) {
  const title = args.join(' ');
  if (!title) { console.log(red('Usage: atlas task add <title>')); return; }
  const data = await apiFetch('/api/tasks', {
    method: 'POST',
    body: JSON.stringify({ title_template: title, title_params: {}, status: 'OPEN', priority: 'NORMAL', due_at: null, linked_thread: null }),
  });
  console.log(green('Task created:'), data?.entity?.entity_id?.slice(0, 8) || 'ok');
}

async function updateTask(id: string, status: string) {
  if (!id) { console.log(red(`Usage: atlas task ${status === 'DONE' ? 'done' : 'start'} <id>`)); return; }
  const data = await apiFetch(`/api/tasks/${id}`, {
    method: 'PUT',
    body: JSON.stringify([{ op: 'replace', path: '/status', value: status }]),
  });
  console.log(green(`Task ${id} → ${status}`));
}

async function showIdeas() {
  const data = await apiFetch('/api/ideas');
  const ideas = Array.isArray(data) ? data : data?.ideas || [];
  if (ideas.length === 0) { console.log('No ideas in registry.'); return; }
  const execNow = ideas.filter((i: any) => i.tier === 'execute_now').slice(0, 5);
  const nextUp = ideas.filter((i: any) => i.tier === 'next_up').slice(0, 5);
  if (execNow.length) {
    console.log(bold(green('Execute Now:')));
    for (const i of execNow) console.log(`  ${i.canonical_title || i.idea_text || 'Untitled'}`);
  }
  if (nextUp.length) {
    console.log(bold(yellow('Next Up:')));
    for (const i of nextUp) console.log(`  ${i.canonical_title || i.idea_text || 'Untitled'}`);
  }
}

async function showBrief() {
  const data = await apiFetch('/api/state/unified');
  const mode = data?.derived?.mode || '--';
  const directive = data?.cognitive?.today?.directive || data?.derived?.primary_order || '--';
  const loops = data?.derived?.open_loops ?? '--';
  const ratio = data?.derived?.closure_ratio != null ? (data.derived.closure_ratio * 100).toFixed(1) + '%' : '--';
  box('DAILY BRIEF', [
    `${bold('Mode:')} ${cyan(mode)}`,
    `${bold('Directive:')} ${directive}`,
    `Open Loops: ${loops}  Closure Ratio: ${ratio}`,
    `Streak: ${data?.derived?.streak_days ?? 0} day(s)`,
  ]);
}

async function startAll() {
  console.log(bold('Starting Atlas...'));
  const services = [
    { name: 'Delta-kernel', port: 3001, dir: 'services\\delta-kernel', cmd: 'npm run api' },
    { name: 'UASC Executor', port: 3008, dir: 'services\\uasc-executor', cmd: 'python server.py --port 3008' },
    { name: 'Cortex', port: 3009, dir: 'services\\cortex', cmd: 'python -m uvicorn cortex.main:app --host 0.0.0.0 --port 3009' },
  ];

  for (const svc of services) {
    try {
      await fetch(`http://localhost:${svc.port}/health`, { signal: AbortSignal.timeout(2000) });
      console.log(`  ${dot(true)} ${svc.name} already running`);
    } catch {
      const fullDir = path.resolve(REPO_ROOT, svc.dir);
      const psCmd = `Set-Location '${fullDir}'; ${svc.cmd}`;
      execCb(`powershell -Command "Start-Process powershell -ArgumentList '-NoExit','-Command','${psCmd.replace(/'/g, "''")}'"`);
      console.log(`  ${yellow('→')} Starting ${svc.name}...`);
    }
  }

  console.log(dim('  Waiting 12 seconds for services to boot...'));
  await new Promise(r => setTimeout(r, 12000));

  const health = await apiFetch('/api/services/health').catch(() => null);
  if (health) {
    for (const [name, info] of Object.entries(health) as [string, any][]) {
      console.log(`  ${dot(info.status === 'up')} ${name}`);
    }
  }

  console.log(dim('  Running cognitive refresh...'));
  try {
    execSync('python refresh.py', { cwd: path.resolve(REPO_ROOT, 'services', 'cognitive-sensor'), timeout: 300000, stdio: 'pipe' });
    console.log(`  ${green('Pipeline complete')}`);
  } catch {
    console.log(`  ${yellow('Pipeline skipped (error)')}`);
  }

  execCb('start http://localhost:3001/cycleboard');
  console.log('');
  await showStatus();
}

async function stopAll() {
  console.log(bold('Stopping Atlas services...'));
  const ports = [3001, 3008, 3009];
  for (const port of ports) {
    try {
      execSync(`powershell -Command "Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"`, { stdio: 'pipe' });
      console.log(`  ${red('■')} Port ${port} stopped`);
    } catch {
      console.log(`  ${dim('○')} Port ${port} not running`);
    }
  }
}

async function runRefresh() {
  console.log(bold('Running cognitive refresh pipeline...'));
  try {
    const output = execSync('python refresh.py', {
      cwd: path.resolve(REPO_ROOT, 'services', 'cognitive-sensor'),
      timeout: 600000,
      encoding: 'utf-8',
    });
    console.log(output);
    console.log(green('Refresh complete.'));
  } catch (e: any) {
    console.log(red('Refresh failed:'), e.message);
  }
}

async function runDashboard() {
  const refresh = async () => {
    process.stdout.write('\x1Bc');
    await showStatus();
    console.log(dim('\nRefreshes every 30s. Press Ctrl+C to exit.'));
  };
  await refresh();
  setInterval(refresh, 30000);
}

// ── CycleBoard state helpers ──

// Peel off historical `{data: ...}` single-key wrappers.
// Server wraps state once (entity.state.data = newState) but older callers
// accidentally double-wrapped by re-sending their whole response as body.
function unwrapCycleboardState(obj: any): any {
  while (obj && typeof obj === 'object' && !Array.isArray(obj)) {
    const keys = Object.keys(obj);
    if (keys.length === 1 && keys[0] === 'data') {
      obj = obj.data;
    } else {
      break;
    }
  }
  return (obj && typeof obj === 'object' && !Array.isArray(obj)) ? obj : {};
}

async function getCycleboardState(): Promise<any> {
  const data = await apiFetch('/api/cycleboard');
  return unwrapCycleboardState(data?.data);
}

async function updateCycleboardState(updates: Record<string, any>): Promise<void> {
  const current = await getCycleboardState();
  const merged = { ...current, ...updates };
  await apiFetch('/api/cycleboard', { method: 'PUT', body: JSON.stringify(merged) });
}

function todayDate(): string {
  return new Date().toISOString().slice(0, 10);
}

// ── Day Plan commands ──

async function showDay(args: string[]) {
  const date = args[0] || todayDate();
  const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan) {
    console.log(yellow(`No plan for ${date}.`));
    console.log(dim(`Create one: atlas day create [A|B|C]`));
    return;
  }
  box(`DAY PLAN — ${date}`, [
    `${bold('Type:')} ${cyan(plan.day_type || '--')}-Day`,
    `${bold('Baseline:')} ${plan.baseline_goal?.text || '--'} ${plan.baseline_goal?.completed ? green('[DONE]') : ''}`,
    `${bold('Stretch:')}  ${plan.stretch_goal?.text || '--'} ${plan.stretch_goal?.completed ? green('[DONE]') : ''}`,
    '---',
    bold('Time Blocks:'),
    ...(plan.time_blocks || []).map((b: any, i: number) =>
      `  ${dim(b.time || '--')} ${b.completed ? green('✓') : '○'} ${b.title || 'Untitled'}`
    ),
    ...(plan.time_blocks?.length ? [] : ['  (none)']),
    '---',
    `${bold('Notes:')} ${plan.notes || '--'}`,
    `${bold('Rating:')} ${plan.rating || '--'}/5`,
  ]);
}

async function createDay(args: string[]) {
  const dayType = (args[0] || 'A').toUpperCase();
  if (!['A', 'B', 'C'].includes(dayType)) { console.log(red('Day type must be A, B, or C')); return; }
  const date = todayDate();
  const state = await getCycleboardState();
  if (!state.DayPlans) state.DayPlans = {};
  if (state.DayPlans[date]) { console.log(yellow(`Plan already exists for ${date}. Use atlas day to view.`)); return; }
  state.DayPlans[date] = {
    id: Date.now().toString(36),
    date,
    day_type: dayType,
    time_blocks: [],
    baseline_goal: { text: '', completed: false },
    stretch_goal: { text: '', completed: false },
    focus_areas: [],
    routines_completed: {},
    notes: '',
    rating: 0,
    progress_snapshots: [],
    final_progress: 0,
  };
  await updateCycleboardState({ DayPlans: state.DayPlans });
  console.log(green(`Created ${dayType}-Day plan for ${date}`));
}

async function addBlock(args: string[]) {
  const time = args[0]; // e.g. "09:00"
  const title = args.slice(1).join(' ');
  if (!time || !title) { console.log(red('Usage: atlas day block <time> <title>')); return; }
  const date = todayDate();
  const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan) { console.log(red(`No plan for today. Run: atlas day create A`)); return; }
  plan.time_blocks.push({ id: Date.now().toString(36), time, title, completed: false });
  plan.time_blocks.sort((a: any, b: any) => (a.time || '').localeCompare(b.time || ''));
  await updateCycleboardState({ DayPlans: state.DayPlans });
  console.log(green(`Added "${title}" at ${time}`));
}

async function completeBlock(args: string[]) {
  const idx = parseInt(args[0]) - 1;
  if (isNaN(idx)) { console.log(red('Usage: atlas day done <block#> (1-based)')); return; }
  const date = todayDate();
  const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan || !plan.time_blocks[idx]) { console.log(red('Block not found')); return; }
  plan.time_blocks[idx].completed = true;
  await updateCycleboardState({ DayPlans: state.DayPlans });
  console.log(green(`Completed: ${plan.time_blocks[idx].title}`));
}

async function setGoal(args: string[]) {
  const type = args[0]; // 'baseline' or 'stretch'
  const text = args.slice(1).join(' ');
  if (!type || !text || !['baseline', 'stretch'].includes(type)) {
    console.log(red('Usage: atlas day goal baseline|stretch <text>')); return;
  }
  const date = todayDate();
  const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan) { console.log(red('No plan for today.')); return; }
  plan[`${type}_goal`] = { text, completed: false };
  await updateCycleboardState({ DayPlans: state.DayPlans });
  console.log(green(`Set ${type} goal: ${text}`));
}

async function rateDay(args: string[]) {
  const rating = parseInt(args[0]);
  if (isNaN(rating) || rating < 1 || rating > 5) { console.log(red('Usage: atlas day rate <1-5>')); return; }
  const date = todayDate();
  const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan) { console.log(red('No plan for today.')); return; }
  plan.rating = rating;
  await updateCycleboardState({ DayPlans: state.DayPlans });
  console.log(green(`Rated today: ${rating}/5`));
}

async function dayCmd(args: string[]) {
  const sub = args[0];
  if (!sub || sub.match(/^\d{4}-\d{2}-\d{2}$/)) return showDay(args);
  if (sub === 'create') return createDay(args.slice(1));
  if (sub === 'block') return addBlock(args.slice(1));
  if (sub === 'done') return completeBlock(args.slice(1));
  if (sub === 'goal') return setGoal(args.slice(1));
  if (sub === 'rate') return rateDay(args.slice(1));
  console.log('Usage: atlas day [date] | create A|B|C | block <time> <title> | done <#> | goal baseline|stretch <text> | rate <1-5>');
}

// ── Routines ──

async function showRoutines() {
  const state = await getCycleboardState();
  const routines = state?.Routine || {};
  const date = todayDate();
  const plan = state?.DayPlans?.[date];
  const completed = plan?.routines_completed || {};

  if (Object.keys(routines).length === 0) { console.log(dim('No routines defined.')); return; }

  console.log(bold('Routines:'));
  for (const [name, steps] of Object.entries(routines) as [string, any[]][]) {
    const routineCompleted = completed[name] || { completed: false, steps: {} };
    const doneCount = Object.values(routineCompleted.steps || {}).filter(Boolean).length;
    console.log(`\n  ${bold(name)} ${doneCount}/${steps.length} ${routineCompleted.completed ? green('[DONE]') : ''}`);
    steps.forEach((step: any, i: number) => {
      const isDone = routineCompleted.steps?.[i] || routineCompleted.steps?.[step] || false;
      console.log(`    ${isDone ? green('✓') : '○'} ${typeof step === 'string' ? step : step.name || step.title || 'Step ' + (i+1)}`);
    });
  }
}

async function completeRoutineStep(args: string[]) {
  const routineName = args[0];
  const stepIdx = parseInt(args[1]) - 1;
  if (!routineName || isNaN(stepIdx)) { console.log(red('Usage: atlas routine done <name> <step#>')); return; }
  const date = todayDate();
  const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan) { console.log(red('No day plan. Create one first: atlas day create A')); return; }
  if (!plan.routines_completed) plan.routines_completed = {};
  if (!plan.routines_completed[routineName]) plan.routines_completed[routineName] = { completed: false, steps: {} };
  plan.routines_completed[routineName].steps[stepIdx] = true;
  const routine = state.Routine?.[routineName] || [];
  const allDone = routine.every((_: any, i: number) => plan.routines_completed[routineName].steps[i]);
  if (allDone) plan.routines_completed[routineName].completed = true;
  await updateCycleboardState({ DayPlans: state.DayPlans });
  console.log(green(`${routineName} step ${stepIdx + 1} done${allDone ? ' — routine complete!' : ''}`));
}

async function routineCmd(args: string[]) {
  if (!args[0] || args[0] === 'list') return showRoutines();
  if (args[0] === 'done') return completeRoutineStep(args.slice(1));
  console.log('Usage: atlas routine [list] | done <name> <step#>');
}

// ── Journal ──

async function showJournal(args: string[]) {
  const state = await getCycleboardState();
  const entries = state?.Journal || [];
  const count = parseInt(args[0]) || 5;
  const recent = entries.slice(-count).reverse();
  if (recent.length === 0) { console.log(dim('No journal entries.')); return; }
  console.log(bold('Journal:'));
  for (const entry of recent) {
    const date = entry.date || entry.createdAt?.slice(0, 10) || '--';
    console.log(`\n  ${dim(date)} ${entry.mood ? `[${entry.mood}]` : ''}`);
    console.log(`  ${entry.content || entry.text || '--'}`);
  }
}

async function addJournal(args: string[]) {
  const text = args.join(' ');
  if (!text) { console.log(red('Usage: atlas journal add <entry text>')); return; }
  const state = await getCycleboardState();
  if (!state.Journal) state.Journal = [];
  state.Journal.push({
    id: Date.now().toString(36),
    date: todayDate(),
    createdAt: new Date().toISOString(),
    content: text,
    mood: null,
  });
  await updateCycleboardState({ Journal: state.Journal });
  console.log(green('Journal entry added.'));
}

async function journalCmd(args: string[]) {
  if (!args[0] || args[0] === 'list') return showJournal(args.slice(1));
  if (args[0] === 'add') return addJournal(args.slice(1));
  console.log('Usage: atlas journal [list] [count] | add <text>');
}

// ── Momentum Wins ──

async function showWins() {
  const state = await getCycleboardState();
  const wins = state?.MomentumWins || [];
  const todayWins = wins.filter((w: any) => w.date === todayDate());
  const recent = wins.slice(-5).reverse();
  console.log(bold(`Momentum Wins`) + ` — ${todayWins.length} today, ${wins.length} total`);
  if (recent.length === 0) { console.log(dim('  No wins yet. Log one: atlas win <description>')); return; }
  for (const w of recent) {
    console.log(`  ${dim(w.date || '--')} ${green('★')} ${w.description || w.text || '--'}`);
  }
}

async function addWin(args: string[]) {
  const text = args.join(' ');
  if (!text) { console.log(red('Usage: atlas win <description>')); return; }
  const state = await getCycleboardState();
  if (!state.MomentumWins) state.MomentumWins = [];
  state.MomentumWins.push({
    id: Date.now().toString(36),
    date: todayDate(),
    timestamp: new Date().toISOString(),
    description: text,
  });
  await updateCycleboardState({ MomentumWins: state.MomentumWins });
  console.log(green(`Win logged: ${text}`));
}

// ── Weekly Focus ──

async function showWeekly() {
  const state = await getCycleboardState();
  const focus = state?.FocusArea || [];
  if (focus.length === 0) { console.log(dim('No focus areas defined.')); return; }
  console.log(bold('Weekly Focus Areas:'));
  for (const area of focus) {
    const tasks = area.tasks || [];
    const done = tasks.filter((t: any) => t.completed || t.status === 'Completed').length;
    console.log(`\n  ${bold(area.name || 'Untitled')} ${dim(`(${done}/${tasks.length})`)}`);
    for (const t of tasks) {
      console.log(`    ${t.completed || t.status === 'Completed' ? green('✓') : '○'} ${t.text || t.task || '--'}`);
    }
  }
}

// ── Reflections ──

async function showReflections(args: string[]) {
  const type = args[0] || 'weekly';
  const state = await getCycleboardState();
  const reflections = state?.Reflections?.[type] || [];
  if (reflections.length === 0) { console.log(dim(`No ${type} reflections.`)); return; }
  console.log(bold(`${type.charAt(0).toUpperCase() + type.slice(1)} Reflections:`));
  for (const r of reflections.slice(-3).reverse()) {
    console.log(`\n  ${dim(r.date || '--')}`);
    console.log(`  ${r.content || r.text || '--'}`);
  }
}

async function addReflection(args: string[]) {
  const type = args[0];
  const text = args.slice(1).join(' ');
  if (!type || !text || !['weekly', 'monthly', 'quarterly', 'yearly'].includes(type)) {
    console.log(red('Usage: atlas reflect add weekly|monthly|quarterly|yearly <text>')); return;
  }
  const state = await getCycleboardState();
  if (!state.Reflections) state.Reflections = { weekly: [], monthly: [], quarterly: [], yearly: [] };
  if (!state.Reflections[type]) state.Reflections[type] = [];
  state.Reflections[type].push({
    id: Date.now().toString(36),
    date: todayDate(),
    createdAt: new Date().toISOString(),
    content: text,
  });
  await updateCycleboardState({ Reflections: state.Reflections });
  console.log(green(`${type} reflection added.`));
}

async function reflectCmd(args: string[]) {
  if (!args[0] || ['weekly', 'monthly', 'quarterly', 'yearly'].includes(args[0])) return showReflections(args);
  if (args[0] === 'add') return addReflection(args.slice(1));
  console.log('Usage: atlas reflect [weekly|monthly|quarterly|yearly] | add <type> <text>');
}

// ── Timeline ──

async function showTimeline(args: string[]) {
  const date = args[0] || todayDate();
  const data = await apiFetch(`/api/timeline/day/${date}`);
  const events = data?.events || [];
  if (events.length === 0) { console.log(dim(`No timeline events for ${date}.`)); return; }
  console.log(bold(`Timeline — ${date}`) + ` (${events.length} events)`);
  for (const e of events.slice(-20)) {
    const time = e.ts ? new Date(e.ts).toLocaleTimeString() : '--';
    console.log(`  ${dim(time)} ${e.type || '--'} ${dim(e.source || '')}`);
  }
}

// ── Statistics ──

async function showStats() {
  const [unified, signals, stats] = await Promise.all([
    apiFetch('/api/state/unified').catch(() => null),
    apiFetch('/api/life-signals').catch(() => null),
    apiFetch('/api/stats').catch(() => null),
  ]);
  const state = await getCycleboardState();
  const tasks = state?.AZTask || [];
  const completedTasks = tasks.filter((t: any) => t.status === 'Completed').length;
  const wins = state?.MomentumWins || [];
  const journalEntries = state?.Journal || [];

  box('STATISTICS', [
    `${bold('Tasks:')} ${completedTasks}/${tasks.length} completed (${tasks.length ? Math.round(completedTasks / tasks.length * 100) : 0}%)`,
    `${bold('Momentum Wins:')} ${wins.length} total, ${wins.filter((w: any) => w.date === todayDate()).length} today`,
    `${bold('Journal Entries:')} ${journalEntries.length}`,
    '---',
    `${bold('Open Loops:')} ${unified?.derived?.open_loops ?? '--'}`,
    `${bold('Closure Ratio:')} ${unified?.derived?.closure_ratio != null ? (unified.derived.closure_ratio * 100).toFixed(1) + '%' : '--'}`,
    `${bold('Streak:')} ${unified?.derived?.streak_days ?? 0} day(s), best: ${unified?.derived?.best_streak ?? 0}`,
    `${bold('Total Closures:')} ${unified?.derived?.total_closures ?? 0}`,
    '---',
    `${bold('Energy:')} ${signals?.energy?.energy_level ?? '--'}  ${bold('Load:')} ${signals?.energy?.mental_load ?? '--'}/10`,
    `${bold('Runway:')} ${signals?.finance?.runway_months ?? '--'} months`,
    `${bold('Skills Util:')} ${signals?.skills?.utilization_pct ?? '--'}%`,
    `${bold('Network:')} ${signals?.network?.collaboration_score ?? '--'}`,
    '---',
    `${bold('Entities:')} ${stats?.entity_count ?? '--'}  ${bold('Deltas:')} ${stats?.delta_count ?? '--'}`,
  ]);
}

// ── Control Panel ──

async function showControl() {
  const [unified, daemon] = await Promise.all([
    apiFetch('/api/state/unified').catch(() => null),
    apiFetch('/api/daemon/status').catch(() => null),
  ]);

  const mode = unified?.derived?.mode || '--';
  const buildAllowed = unified?.derived?.build_allowed ?? false;
  const violations = unified?.derived?.violations_count ?? 0;
  const overrides = unified?.derived?.overrides_count ?? 0;
  const enforcement = unified?.derived?.enforcement_level ?? 0;
  const overrideAvailable = unified?.derived?.override_available ?? false;

  box('CONTROL PANEL', [
    `${bold('Mode:')} ${cyan(mode)}  ${bold('Build:')} ${buildAllowed ? green('ALLOWED') : red('BLOCKED')}`,
    `${bold('Enforcement Level:')} ${enforcement}/3`,
    `${bold('Violations:')} ${violations}  ${bold('Overrides:')} ${overrides}`,
    `${bold('Override Available:')} ${overrideAvailable ? green('YES') : red('NO')}`,
    '---',
    bold('Daemon Jobs:'),
    ...(daemon?.jobs ? Object.entries(daemon.jobs).map(([name, info]: [string, any]) =>
      `  ${name.padEnd(18)} ${info.last_run ? dim(new Date(info.last_run).toLocaleString()) : dim('never')}`
    ) : ['  (daemon not responding)']),
  ]);
}

// ── Settings ──

async function showSettings() {
  const state = await getCycleboardState();
  const settings = state?.Settings || {};
  console.log(bold('Settings:'));
  for (const [key, value] of Object.entries(settings)) {
    console.log(`  ${key.padEnd(20)} ${String(value)}`);
  }
}

// ── Enhanced Directive (Strategic Banner) ──

async function showDirectiveEnhanced() {
  const [unified, strategic, governor] = await Promise.all([
    apiFetch('/api/state/unified').catch(() => null),
    Promise.resolve(readBrainJson('strategic_priorities.json')),
    Promise.resolve(readBrainJson('governor_headline.json')),
  ]);

  const mode = unified?.derived?.mode || '--';
  const risk = unified?.derived?.open_loops > 10 ? 'HIGH' : unified?.derived?.open_loops > 5 ? 'MEDIUM' : 'LOW';
  const loops = unified?.derived?.open_loops ?? '--';
  const buildAllowed = unified?.derived?.build_allowed ?? false;
  const directive = unified?.cognitive?.today?.directive || unified?.derived?.primary_order || '--';

  const lines: string[] = [
    `${bold('Mode:')} ${modeColor(mode)}    ${bold('Risk:')} ${risk === 'HIGH' ? red(risk) : risk === 'MEDIUM' ? yellow(risk) : green(risk)}    ${bold('Loops:')} ${loops}    ${bold('Build:')} ${buildAllowed ? green('YES') : red('NO')}`,
    '---',
    `${bold('Action:')}  ${directive}`,
  ];

  // Strategic priorities
  const dd = strategic?.daily_directive;
  if (dd) {
    if (dd.primary_focus) lines.push(`${bold('Focus:')}   ${dd.primary_focus}`);
    if (dd.primary_action) lines.push(`${bold('Action:')}  ${dd.primary_action}`);
    if (dd.suggested_deep_block_mins) lines.push(`${bold('Deep:')}    ${dd.suggested_deep_block_mins} min suggested`);
    if (dd.stretch_goal) lines.push(`${bold('Stretch:')} ${dd.stretch_goal}`);
  }

  // Top clusters
  const clusters = strategic?.top_clusters?.slice(0, 3);
  if (clusters?.length) {
    lines.push('---');
    lines.push(bold('Top Clusters:'));
    for (const c of clusters) {
      const gap = c.gap === 'HIGH' ? red(c.gap) : c.gap === 'MEDIUM' ? yellow(c.gap) : green(c.gap || '--');
      lines.push(`  ${c.label || c.cluster_id || '--'}  leverage=${c.normalized_leverage?.toFixed(2) ?? '--'}  gap=${gap}`);
    }
  }

  // Governor warnings
  if (governor) {
    lines.push('---');
    if (governor.warning) lines.push(`${bold('Warning:')}  ${yellow(governor.warning)}`);
    if (governor.top_move) lines.push(`${bold('Top Move:')} ${governor.top_move}`);
    if (governor.confrontation) lines.push(`${bold('Confront:')} ${red(governor.confrontation)}`);
    const alerts = governor.drift_alerts || [];
    for (const a of alerts) {
      lines.push(`  ${red('⚠')} ${a.type}: ${a.message}`);
    }
  }

  box('DIRECTIVE', lines);
}

// ── Cognitive / Drift / Radar ──

async function showCognitive() {
  const [unified, governor] = await Promise.all([
    apiFetch('/api/state/unified').catch(() => null),
    Promise.resolve(readBrainJson('governor_headline.json')),
  ]);

  const cogState = unified?.cognitive?.cognitive_state;
  const mode = unified?.derived?.mode || '--';
  const closureRatio = normalizePct(unified?.derived?.closure_ratio);
  const closureQuality = cogState?.closure?.closure_quality != null ? cogState.closure.closure_quality.toFixed(1) + '%' : governor?.closure_quality != null ? governor.closure_quality.toFixed(1) + '%' : '--';
  const driftScore = governor?.drift_score ?? '--';
  const compliance = governor?.compliance_rate != null ? governor.compliance_rate + '%' : '--';

  const lines: string[] = [
    `${bold('Mode:')} ${modeColor(mode)}    ${bold('Closure:')} ${closureRatio}    ${bold('Quality:')} ${closureQuality}`,
    `${bold('Drift Score:')} ${typeof driftScore === 'number' && driftScore >= 3 ? red(String(driftScore)) : String(driftScore)}    ${bold('Compliance:')} ${compliance}`,
  ];

  // Drift topics
  const drift = cogState?.drift;
  if (drift && typeof drift === 'object') {
    const entries = Object.entries(drift).sort((a: any, b: any) => b[1] - a[1]).slice(0, 10);
    if (entries.length) {
      lines.push('---');
      lines.push(bold('Drift Topics:'));
      const maxVal = (entries[0] as any)[1] || 1;
      for (const [word, weight] of entries) {
        const w = weight as number;
        const barLen = Math.round((w / maxVal) * 15);
        lines.push(`  ${word.padEnd(15)} ${cyan('█'.repeat(barLen))} ${w.toFixed(1)}`);
      }
    }
  }

  // Open loops summary
  const loops = cogState?.loops?.slice(0, 5);
  if (loops?.length) {
    lines.push('---');
    lines.push(bold('Top Open Loops:'));
    for (const loop of loops) {
      lines.push(`  ${dim(String(loop.convo_id || '--').slice(0, 6).padEnd(6))} ${(loop.title || 'Untitled').slice(0, 35).padEnd(35)} ${yellow('score=' + loop.score)}`);
    }
  }

  // Alerts
  const alerts = governor?.drift_alerts || [];
  if (alerts.length || governor?.warning || governor?.top_move) {
    lines.push('---');
    for (const a of alerts) lines.push(`  ${red('⚠')} ${a.type}: ${a.message}`);
    if (governor?.top_move) lines.push(`${bold('Top Move:')} ${governor.top_move}`);
    if (governor?.warning) lines.push(`${bold('Warning:')}  ${yellow(governor.warning)}`);
  }

  box('COGNITIVE STATE', lines);
}

// ── OSINT Feed ──

async function showOsint() {
  const feed = readBrainJson('osint_feed.json');
  if (!feed) { console.log(dim('No OSINT data. Brain file missing: brain/osint_feed.json')); return; }

  const status = feed.status || 'unknown';
  const updated = feed.generated_at || feed.generated || feed.updated_at;
  const statusDot = status === 'online' ? green('●') : red('●');

  const lines: string[] = [
    `${bold('Status:')} ${statusDot} ${status.toUpperCase()}    ${bold('Updated:')} ${ageText(updated)}`,
  ];

  // Highlights
  const highlights = feed.highlights || [];
  if (highlights.length) {
    lines.push('---');
    lines.push(bold('Highlights:'));
    for (const h of highlights.slice(0, 5)) lines.push(`  ${dim('•')} ${typeof h === 'string' ? h : h.text || h.title || '--'}`);
  }

  // Markets
  const market = feed.market;
  if (market) {
    lines.push('---');
    const parts: string[] = [];
    if (market.indexes) for (const [k, v] of Object.entries(market.indexes)) parts.push(`${k}: ${v}`);
    if (market.crypto) for (const [k, v] of Object.entries(market.crypto)) parts.push(`${k}: $${v}`);
    if (market.vix != null) parts.push(`VIX: ${market.vix}`);
    if (market.gold != null) parts.push(`Gold: $${market.gold}`);
    if (parts.length) lines.push(`${bold('Markets:')}  ${parts.join('  ')}`);
  }

  // Economic
  const econ = feed.economic;
  if (econ) {
    const parts: string[] = [];
    for (const [k, v] of Object.entries(econ)) parts.push(`${k}: ${v}`);
    if (parts.length) lines.push(`${bold('Economic:')} ${parts.join('  ')}`);
  }

  // News
  const news = feed.news;
  if (Array.isArray(news) && news.length) {
    lines.push('---');
    lines.push(bold('News:'));
    for (const n of news.slice(0, 5)) {
      const urgent = n.urgent ? red('[!] ') : '    ';
      lines.push(`${urgent}${typeof n === 'string' ? n : n.title || n.text || '--'}`);
    }
  }

  // Sentiment
  if (feed.sentiment && typeof feed.sentiment === 'string') lines.push(`${bold('Sentiment:')} ${feed.sentiment}`);
  else if (feed.sentiment && typeof feed.sentiment === 'object' && Object.keys(feed.sentiment).length) {
    const parts = Object.entries(feed.sentiment).map(([k, v]) => `${k}: ${v}`).join('  ');
    lines.push(`${bold('Sentiment:')} ${parts}`);
  }

  box('OSINT FEED', lines);
}

// ── A-Z Tasks ──

async function showAZ(args: string[]) {
  const state = await getCycleboardState().catch(() => { console.log(red('Delta-kernel not running.')); return null; });
  if (!state) return;
  const tasks = state?.AZTask || [];
  const filter = parseFlag(args, 'status');

  let filtered = tasks;
  if (filter === 'completed') filtered = tasks.filter((t: any) => t.status === 'Completed');
  else if (filter === 'in-progress') filtered = tasks.filter((t: any) => t.status === 'In Progress');
  else if (filter === 'not-started') filtered = tasks.filter((t: any) => !t.status || t.status === 'Not Started');

  const total = tasks.length;
  const completed = tasks.filter((t: any) => t.status === 'Completed').length;
  const inProgress = tasks.filter((t: any) => t.status === 'In Progress').length;
  const notStarted = total - completed - inProgress;
  const pct = total ? Math.round((completed / total) * 100) : 0;

  const lines: string[] = [
    `Total: ${total}  ${green('Done: ' + completed)}  ${yellow('Active: ' + inProgress)}  ${dim('Todo: ' + notStarted)}`,
    progressBar(pct),
  ];

  if (filtered.length === 0) {
    lines.push('---');
    lines.push(dim('No tasks' + (filter ? ` with status "${filter}"` : '') + '.'));
  } else {
    lines.push('---');
    // Group by letter
    const grouped: Record<string, any[]> = {};
    for (const t of filtered) {
      const letter = (t.letter || '?').toUpperCase();
      if (!grouped[letter]) grouped[letter] = [];
      grouped[letter].push(t);
    }
    const sortedLetters = Object.keys(grouped).sort();
    for (const letter of sortedLetters) {
      for (const t of grouped[letter]) {
        const icon = t.status === 'Completed' ? green('✓') : t.status === 'In Progress' ? yellow('▸') : '○';
        const task = t.status === 'Completed' ? dim(t.task || '--') : (t.task || '--');
        const notes = t.notes ? dim(` (${t.notes.slice(0, 25)})`) : '';
        lines.push(`  ${bold(letter)}  ${icon}  ${task}${notes}`);
      }
    }
  }

  box('A-Z TASKS', lines);
}

async function addAZTask(args: string[]) {
  const letter = args[0]?.toUpperCase();
  const task = args.slice(1).join(' ');
  if (!letter || !task || letter.length !== 1) { console.log(red('Usage: atlas az add <letter> <task>')); return; }
  const state = await getCycleboardState();
  if (!state.AZTask) state.AZTask = [];
  state.AZTask.push({
    id: Date.now().toString(36),
    letter,
    task,
    status: 'Not Started',
    notes: '',
    createdAt: new Date().toISOString(),
  });
  await updateCycleboardState({ AZTask: state.AZTask });
  console.log(green(`Added ${letter}: ${task}`));
}

async function toggleAZTask(args: string[], targetStatus: string) {
  const query = args[0];
  if (!query) { console.log(red(`Usage: atlas az ${targetStatus === 'Completed' ? 'done' : 'start'} <letter-or-id>`)); return; }
  const state = await getCycleboardState();
  const tasks = state?.AZTask || [];
  const match = tasks.find((t: any) =>
    t.id === query || (t.letter || '').toUpperCase() === query.toUpperCase()
  );
  if (!match) { console.log(red(`No A-Z task matching "${query}"`)); return; }
  match.status = targetStatus;
  await updateCycleboardState({ AZTask: tasks });
  console.log(green(`${match.letter}: ${match.task} → ${targetStatus}`));
}

async function azCmd(args: string[]) {
  if (!args[0] || args[0].startsWith('--')) return showAZ(args);
  if (args[0] === 'add') return addAZTask(args.slice(1));
  if (args[0] === 'done') return toggleAZTask(args.slice(1), 'Completed');
  if (args[0] === 'start') return toggleAZTask(args.slice(1), 'In Progress');
  console.log('Usage: atlas az [--status all|completed|in-progress|not-started] | add <letter> <task> | done <letter> | start <letter>');
}

// ── Calendar ──

async function showCalendar(args: string[]) {
  const sub = args[0];
  if (sub === 'week') return showCalendarWeek(args[1]);
  return showCalendarMonth(args[0]);
}

async function showCalendarMonth(targetDate?: string) {
  const state = await getCycleboardState().catch(() => { console.log(red('Delta-kernel not running.')); return null; });
  if (!state) return;
  const today = todayDate();
  const ref = targetDate && /^\d{4}-\d{2}-\d{2}$/.test(targetDate) ? targetDate : today;
  const [year, month] = ref.split('-').map(Number);
  const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];

  const firstDay = new Date(year, month - 1, 1);
  const daysInMonth = new Date(year, month, 0).getDate();
  const startDow = firstDay.getDay();

  console.log(bold(`       ${monthNames[month - 1]} ${year}`));
  console.log(dim(' Su  Mo  Tu  We  Th  Fr  Sa'));

  let row = '    '.repeat(startDow);
  for (let d = 1; d <= daysInMonth; d++) {
    const ds = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const plan = state?.DayPlans?.[ds];
    const blocks = plan?.time_blocks || [];
    const done = blocks.filter((b: any) => b.completed).length;
    const pct = blocks.length ? Math.round((done / blocks.length) * 100) : 0;
    const isToday = ds === today;

    let cell: string;
    if (isToday) {
      cell = `${bold(cyan('[' + String(d).padStart(2) + ']'))}`;
    } else if (plan && pct >= 70) {
      cell = `${green(' ' + String(d).padStart(2) + ' ')}`;
    } else if (plan && pct >= 50) {
      cell = `${yellow(' ' + String(d).padStart(2) + ' ')}`;
    } else if (plan) {
      cell = `${dim(' ' + String(d).padStart(2) + ' ')}`;
    } else {
      cell = ` ${String(d).padStart(2)} `;
    }

    row += cell;
    if ((startDow + d) % 7 === 0 || d === daysInMonth) {
      console.log(row);
      row = '';
    }
  }

  console.log('');
  console.log(`${green('■')}${dim('=70%+')} ${yellow('■')}${dim('=50%+')} ${cyan('[n]')}${dim('=today')}`);

  // Month summary
  const planned = Object.keys(state?.DayPlans || {}).filter(k => k.startsWith(`${year}-${String(month).padStart(2, '0')}`));
  if (planned.length) {
    const avgPct = Math.round(planned.reduce((sum, k) => {
      const p = state.DayPlans[k];
      const b = p?.time_blocks || [];
      const d = b.filter((x: any) => x.completed).length;
      return sum + (b.length ? (d / b.length) * 100 : 0);
    }, 0) / planned.length);
    console.log(dim(`  ${planned.length} days planned · avg ${avgPct}% complete`));
  }
}

async function showCalendarWeek(targetDate?: string) {
  const state = await getCycleboardState().catch(() => { console.log(red('Delta-kernel not running.')); return null; });
  if (!state) return;
  const today = todayDate();
  const ref = targetDate && /^\d{4}-\d{2}-\d{2}$/.test(targetDate) ? targetDate : today;
  const d = new Date(ref + 'T12:00:00');
  const weekStart = new Date(d);
  weekStart.setDate(d.getDate() - d.getDay());
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  console.log(bold(`Week of ${weekStart.toISOString().slice(0, 10)}`));
  console.log('');

  for (let i = 0; i < 7; i++) {
    const wd = new Date(weekStart);
    wd.setDate(weekStart.getDate() + i);
    const ds = wd.toISOString().slice(0, 10);
    const plan = state?.DayPlans?.[ds];
    const isToday = ds === today;
    const prefix = isToday ? cyan('>') : ' ';
    const dayLabel = `${dayNames[i]} ${String(wd.getDate()).padStart(2)}`;

    if (!plan) {
      console.log(`${prefix} ${dim(dayLabel + '  --  no plan')}`);
    } else {
      const blocks = plan.time_blocks || [];
      const done = blocks.filter((b: any) => b.completed).length;
      const pct = blocks.length ? Math.round((done / blocks.length) * 100) : 0;
      const type = plan.day_type || '?';
      const tc = type === 'A' ? cyan : type === 'B' ? yellow : red;
      console.log(`${prefix} ${bold(dayLabel)}  ${tc(type)}  ${progressBar(pct, 15)}  ${dim(done + '/' + blocks.length + ' blocks')}`);
    }
  }
  console.log('');
}

// ── Home Dashboard ──

async function showHome() {
  const [unified, health, signals, ideas, state] = await Promise.all([
    apiFetch('/api/state/unified').catch(() => null),
    apiFetch('/api/services/health').catch(() => null),
    getSignals().catch(() => null),
    apiFetch('/api/ideas').catch(() => null),
    getCycleboardState().catch(() => ({})),
  ]);
  const governor = readBrainJson('governor_headline.json');

  const today = todayDate();
  const mode = unified?.derived?.mode || '--';
  const risk = unified?.derived?.open_loops > 10 ? 'HIGH' : unified?.derived?.open_loops > 5 ? 'MEDIUM' : 'LOW';
  const loops = unified?.derived?.open_loops ?? '--';
  const directiveRaw = unified?.cognitive?.today?.directive || unified?.derived?.primary_order || '--';
  const directive = (() => {
    if (Array.isArray(directiveRaw)) return String(directiveRaw[0] ?? '--');
    if (directiveRaw && typeof directiveRaw === 'object') {
      const o: any = directiveRaw;
      return String(o.text ?? o.title ?? o.directive ?? o.order ?? o.description ?? '--');
    }
    return String(directiveRaw);
  })();
  const streak = unified?.derived?.streak_days ?? 0;

  // Today's plan
  const plan = state?.DayPlans?.[today];
  const blocks = plan?.time_blocks || [];
  const blocksDone = blocks.filter((b: any) => b.completed).length;
  const dayPct = blocks.length ? Math.round((blocksDone / blocks.length) * 100) : 0;
  const dayType = plan?.day_type || '--';

  // A-Z summary
  const azTasks = state?.AZTask || [];
  const azDone = azTasks.filter((t: any) => t.status === 'Completed').length;
  const azPct = azTasks.length ? Math.round((azDone / azTasks.length) * 100) : 0;

  // Wins
  const wins = (state?.MomentumWins || []).filter((w: any) => w.date === today).length;

  const dateStr = new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });

  const lines: string[] = [
    `${bold('Mode:')} ${modeColor(mode)}    ${bold('Risk:')} ${risk === 'HIGH' ? red(risk) : risk === 'MEDIUM' ? yellow(risk) : green(risk)}    ${bold('Loops:')} ${loops}`,
    `${bold('Directive:')} ${directive.slice(0, 48)}`,
    '---',
    `${bold('Today:')} ${dayType}-Day  ${plan ? progressBar(dayPct, 15) : dim('no plan')}  ${dim(blocksDone + '/' + blocks.length + ' blocks')}`,
    `${bold('A-Z:')} ${azDone}/${azTasks.length} (${azPct}%)   ${bold('Streak:')} ${streak}d   ${bold('Wins:')} ${wins} today`,
  ];

  // Life signals
  const e = signals?.energy;
  const f = signals?.finance;
  const s = signals?.skills;
  const n = signals?.network;
  if (e || f || s || n) {
    lines.push('---');
    const parts: string[] = [];
    if (e) parts.push(`Energy: ${e.energy_level ?? '--'}  Load: ${e.mental_load ?? '--'}/10  Sleep: ${e.sleep_quality ?? '--'}/5`);
    if (f) parts.push(`Runway: ${f.runway_months ?? '--'}mo`);
    if (parts.length) lines.push(parts.join('  '));
    const parts2: string[] = [];
    if (s) parts2.push(`Skills: ${s.utilization_pct ?? '--'}%`);
    if (n) parts2.push(`Network: ${n.collaboration_score ?? '--'}`);
    if (e?.life_phase) parts2.push(`Phase: ${e.life_phase}`);
    if (parts2.length) lines.push(parts2.join('  '));
  }

  // Ideas
  const ideaList = Array.isArray(ideas) ? ideas : ideas?.ideas || [];
  const execNow = ideaList.filter((i: any) => i.tier === 'execute_now').slice(0, 3);
  if (execNow.length) {
    lines.push('---');
    lines.push(bold('Ideas:') + ' ' + execNow.map((i: any) => dim('• ') + (i.canonical_title || i.idea_text || '--').slice(0, 30)).join('  '));
  }

  // System pulse
  if (governor) {
    lines.push('---');
    const pulse: string[] = [];
    if (governor.drift_score != null) pulse.push(`drift=${governor.drift_score}`);
    if (governor.compliance_rate != null) pulse.push(`compliance=${governor.compliance_rate}%`);
    if (governor.top_move) pulse.push(`top_move=${governor.top_move.slice(0, 25)}`);
    lines.push(`${bold('Pulse:')} ${pulse.join('  ')}`);
  }

  // Service health
  if (health) {
    lines.push('---');
    const svcs = Object.entries(health).map(([name, info]: [string, any]) =>
      `${dot(info.status === 'up')} ${name}`
    ).join('  ');
    lines.push(`${bold('Services:')} ${svcs}`);
  }

  box(`ATLAS HOME — ${dateStr}`, lines);
}

async function daemonCmd(args: string[]) {
  const sub = args[0];
  if (sub === 'status') {
    const data = await apiFetch('/api/daemon/status');
    console.log(bold('Daemon Status:'));
    if (data?.jobs) {
      for (const [name, info] of Object.entries(data.jobs) as [string, any][]) {
        console.log(`  ${name.padEnd(20)} last: ${info.last_run || '--'}`);
      }
    } else {
      console.log(JSON.stringify(data, null, 2));
    }
  } else if (sub === 'run' && args[1]) {
    const data = await apiFetch('/api/daemon/run', { method: 'POST', body: JSON.stringify({ job: args[1] }) });
    console.log(data?.ok ? green(`Job ${args[1]} executed`) : red(JSON.stringify(data)));
  } else {
    console.log('Usage: atlas daemon status | atlas daemon run <job>');
  }
}

function showHelp() {
  console.log(bold('Atlas CLI') + ' — Unified Pre Atlas interface\n');
  const cmds = [
    [dim('Dashboard'), ''],
    ['home', 'Full dashboard (mode, plan, signals, ideas, pulse)'],
    ['status', 'System status (mode, health, signals, loops)'],
    ['dashboard', 'Live terminal dashboard (refreshes every 30s)'],
    ['', ''],
    [dim('CycleBoard'), ''],
    ['day', 'Show today\'s plan'],
    ['day create A|B|C', 'Create today\'s plan'],
    ['day block <time> <title>', 'Add time block'],
    ['day done <block#>', 'Complete a time block'],
    ['day goal baseline|stretch', 'Set daily goal'],
    ['day rate <1-5>', 'Rate today'],
    ['calendar [month|week]', 'Calendar month grid or week view'],
    ['az', 'A-Z task list (--status filter)'],
    ['az add <letter> <task>', 'Add A-Z task'],
    ['az done|start <letter>', 'Complete or start A-Z task'],
    ['routine', 'Show routines + progress'],
    ['routine done <name> <step#>', 'Complete routine step'],
    ['journal', 'Show recent journal entries'],
    ['journal add <text>', 'Add journal entry'],
    ['win <description>', 'Log a momentum win'],
    ['wins', 'Show momentum wins'],
    ['weekly', 'Show weekly focus areas'],
    ['reflect', 'Show reflections'],
    ['reflect add <type> <text>', 'Add reflection'],
    ['timeline [date]', 'Show timeline events'],
    ['stats', 'Show statistics'],
    ['settings', 'Show settings'],
    ['', ''],
    [dim('Brain'), ''],
    ['directive', 'Cognitive + strategic directive'],
    ['cognitive', 'Drift score, topics, alerts, compliance'],
    ['osint', 'OSINT intelligence feed'],
    ['ideas', 'Show top ideas from registry'],
    ['brief', 'Show daily brief'],
    ['loops', 'List open loops'],
    ['close <id>', 'Close a loop'],
    ['archive <id>', 'Archive a loop'],
    ['', ''],
    [dim('Signals'), ''],
    ['energy', 'Show energy (or: energy <N> --load --sleep)'],
    ['finance', 'Show finance (or: --runway --income --expenses)'],
    ['skills', 'Show skills (or: --util --learning --mastery)'],
    ['network', 'Show network (or: --collab --relationships)'],
    ['', ''],
    [dim('System'), ''],
    ['health', 'Show service health'],
    ['control', 'Show governance control panel'],
    ['tasks', 'List delta tasks'],
    ['task add|done|start', 'Manage delta tasks'],
    ['mode', 'Show current mode + reason'],
    ['refresh', 'Run cognitive pipeline'],
    ['start', 'Start all services'],
    ['stop', 'Stop all services'],
    ['daemon status|run', 'Daemon management'],
    ['help', 'Show this help'],
  ];
  for (const [cmd, desc] of cmds) {
    if (!cmd) { console.log(''); continue; }
    console.log(`  ${cyan(cmd.padEnd(22))} ${desc}`);
  }
}

// ── Dispatcher ──

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];
  const rest = args.slice(1);

  switch (command) {
    case 'status': return showStatus();
    case 'mode': return showMode();
    case 'directive': case 'strategy': return showDirectiveEnhanced();
    case 'health': return showHealth();
    case 'energy': return energyCmd(rest);
    case 'finance': return financeCmd(rest);
    case 'skills': return skillsCmd(rest);
    case 'network': return networkCmd(rest);
    case 'cognitive': case 'drift': case 'radar': return showCognitive();
    case 'osint': return showOsint();
    case 'az': case 'a-z': case 'atoz': return azCmd(rest);
    case 'calendar': case 'cal': return showCalendar(rest);
    case 'home': return showHome();
    case 'loops': return showLoops();
    case 'lifecycle': return showLifecycle();
    case 'close': return closeLoop(rest, 'closed');
    case 'archive': return closeLoop(rest, 'archived');
    case 'tasks': return showTasks();
    case 'task': {
      if (rest[0] === 'add') return addTask(rest.slice(1));
      if (rest[0] === 'done') return updateTask(rest[1], 'DONE');
      if (rest[0] === 'start') return updateTask(rest[1], 'IN_PROGRESS');
      console.log('Usage: atlas task add|done|start <arg>');
      return;
    }
    case 'ideas': return showIdeas();
    case 'brief': return showBrief();
    case 'day': return dayCmd(rest);
    case 'routine': return routineCmd(rest);
    case 'journal': return journalCmd(rest);
    case 'win': return addWin(rest);
    case 'wins': return showWins();
    case 'weekly': return showWeekly();
    case 'reflect': return reflectCmd(rest);
    case 'timeline': return showTimeline(rest);
    case 'stats': return showStats();
    case 'control': return showControl();
    case 'settings': return showSettings();
    case 'start': return startAll();
    case 'stop': return stopAll();
    case 'refresh': return runRefresh();
    case 'dashboard': return runDashboard();
    case 'daemon': return daemonCmd(rest);
    case 'help':
    case undefined: return showHelp();
    default:
      console.log(red(`Unknown command: ${command}`) + '. Run ' + cyan('atlas help'));
      process.exit(1);
  }
}

main().catch(err => { console.error(red('Error:'), err.message); process.exit(1); });
