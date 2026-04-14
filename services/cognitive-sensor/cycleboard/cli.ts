#!/usr/bin/env node
/**
 * CycleBoard CLI
 * Thin command-line interface to CycleBoard state via delta-kernel API.
 * Usage: npx tsx cli.ts <command> [args]
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const API = 'http://localhost:3001';

// === API Key ===
const __cli_filename = fileURLToPath(import.meta.url);
const __cli_dirname = path.dirname(__cli_filename);

function loadApiKey(): string | null {
  // Walk up from cli.ts location to find .aegis-tenant-key
  const candidates = [
    path.resolve(__cli_dirname, '../../..', '.aegis-tenant-key'),  // cycleboard -> cognitive-sensor -> services -> repo root
    path.resolve(__cli_dirname, '../../../..', '.aegis-tenant-key'),
  ];
  for (const p of candidates) {
    try { return fs.readFileSync(p, 'utf-8').trim(); } catch {}
  }
  return null;
}

const API_KEY = loadApiKey();
const AUTH_HEADERS: Record<string, string> = API_KEY
  ? { 'Authorization': `Bearer ${API_KEY}` }
  : {};

// === ANSI Colors (matches delta-kernel renderer.ts) ===
const C = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  white: '\x1b[37m',
  bgRed: '\x1b[41m',
  bgGreen: '\x1b[42m',
  bgYellow: '\x1b[43m',
  bgBlue: '\x1b[44m',
};

// === Day Type Templates (mirrors state.js defaults) ===
const TEMPLATES: Record<string, { name: string; blocks: { time: string; title: string }[]; baseline: string; stretch: string }> = {
  A: {
    name: 'Optimal Day',
    blocks: [
      { time: '6:00 AM', title: 'Morning Routine' },
      { time: '7:00 AM', title: 'Commute / Prep' },
      { time: '7:30 AM', title: 'Deep Work Block 1' },
      { time: '9:00 AM', title: 'Break / Recharge' },
      { time: '9:15 AM', title: 'Deep Work Block 2' },
      { time: '10:45 AM', title: 'Admin / Email' },
      { time: '11:15 AM', title: 'Deep Work Block 3' },
      { time: '12:45 PM', title: 'Lunch Break' },
      { time: '1:30 PM', title: 'Deep Work Block 4' },
      { time: '3:00 PM', title: 'Meetings / Collaboration' },
      { time: '4:00 PM', title: 'Wrap-up / Planning' },
      { time: '4:30 PM', title: 'Evening Routine' },
    ],
    baseline: 'Complete 4 deep work blocks',
    stretch: 'Clear inbox + bonus task',
  },
  B: {
    name: 'Low Energy Day',
    blocks: [
      { time: '7:00 AM', title: 'Light Morning Routine' },
      { time: '7:45 AM', title: 'Easy Start Task' },
      { time: '8:30 AM', title: 'Focus Block 1' },
      { time: '9:30 AM', title: 'Break / Walk' },
      { time: '9:50 AM', title: 'Focus Block 2' },
      { time: '10:50 AM', title: 'Admin / Light Tasks' },
      { time: '11:30 AM', title: 'Early Lunch' },
      { time: '12:30 PM', title: 'Focus Block 3' },
      { time: '1:30 PM', title: 'Rest / Recharge' },
      { time: '2:00 PM', title: 'Light Work / Wrap-up' },
      { time: '3:00 PM', title: 'Evening Routine' },
    ],
    baseline: 'Complete 3 focus blocks',
    stretch: 'One bonus task if energy allows',
  },
  C: {
    name: 'Chaos Day',
    blocks: [
      { time: '8:00 AM', title: 'Minimal Morning' },
      { time: '8:30 AM', title: 'Identify ONE Priority' },
      { time: '8:45 AM', title: 'Priority Task' },
      { time: '10:15 AM', title: 'Break / Assess' },
      { time: '10:30 AM', title: 'Continue Priority or Pivot' },
      { time: '11:30 AM', title: 'Lunch / Reset' },
      { time: '12:30 PM', title: 'Damage Control / Urgent Only' },
      { time: '2:00 PM', title: 'Wrap Minimum Viable Day' },
      { time: '2:30 PM', title: 'Rest / Tomorrow Prep' },
    ],
    baseline: 'Complete ONE priority task',
    stretch: 'Survive and reset for tomorrow',
  },
};

// === Helpers ===

function genId(): string {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function resolveDate(input: string): string {
  if (input === 'today') return todayISO();
  if (input === 'tomorrow') {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().slice(0, 10);
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(input)) return input;
  console.error(`${C.red}Invalid date: ${input}. Use YYYY-MM-DD, "today", or "tomorrow".${C.reset}`);
  process.exit(1);
}

function formatDate(iso: string): string {
  const d = new Date(iso + 'T12:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
}

function progressBar(pct: number, width = 30): string {
  const filled = Math.round((pct / 100) * width);
  const empty = width - filled;
  const color = pct >= 70 ? C.green : pct >= 50 ? C.yellow : C.dim;
  return `${color}${'█'.repeat(filled)}${'░'.repeat(empty)}${C.reset} ${pct}%`;
}

function box(title: string, lines: string[], width = 50): string {
  const hr = '─'.repeat(width - 2);
  const pad = (s: string) => {
    const stripped = s.replace(/\x1b\[[0-9;]*m/g, '');
    const remaining = width - 4 - stripped.length;
    return `│ ${s}${' '.repeat(Math.max(0, remaining))} │`;
  };
  const out: string[] = [];
  out.push(`┌${hr}┐`);
  if (title) {
    out.push(pad(`${C.bold}${title}${C.reset}`));
    out.push(`├${hr}┤`);
  }
  for (const line of lines) out.push(pad(line));
  out.push(`└${hr}┘`);
  return out.join('\n');
}

// === API ===

async function fetchState(): Promise<any> {
  try {
    const res = await fetch(`${API}/api/cycleboard`, { headers: AUTH_HEADERS });
    if (res.status === 401) {
      console.error(`${C.red}Authentication failed. Check .aegis-tenant-key${C.reset}`);
      process.exit(1);
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    return json.data?.data || json.data || null;
  } catch (e: any) {
    if (e?.message?.includes('Authentication')) throw e;
    console.error(`${C.red}Delta-kernel not running.${C.reset}`);
    console.error(`${C.dim}Start with: cd services/delta-kernel && npm run api${C.reset}`);
    process.exit(1);
  }
}

async function saveState(state: any): Promise<void> {
  const res = await fetch(`${API}/api/cycleboard`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...AUTH_HEADERS },
    body: JSON.stringify(state),
  });
  if (res.status === 401) {
    console.error(`${C.red}Authentication failed. Check .aegis-tenant-key${C.reset}`);
    process.exit(1);
  }
  if (!res.ok) {
    console.error(`${C.red}Failed to save state: HTTP ${res.status}${C.reset}`);
    process.exit(1);
  }
}

async function fetchSystemState(): Promise<any> {
  try {
    const res = await fetch(`${API}/api/state`, { headers: AUTH_HEADERS });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function getDayPlan(state: any, date: string): any {
  return state?.DayPlans?.[date] || null;
}

function calcProgress(plan: any): number {
  if (!plan) return 0;
  const blocks = plan.time_blocks || [];
  const total = blocks.length;
  const done = blocks.filter((b: any) => b.completed).length;
  return total ? Math.round((done / total) * 100) : 0;
}

// === Commands ===

async function cmdToday() {
  const state = await fetchState();
  const date = todayISO();
  const plan = getDayPlan(state, date);
  const sys = await fetchSystemState();

  const header = [
    `${C.cyan}CYCLEBOARD${C.reset}          ${formatDate(date)}`,
  ];
  if (sys) {
    const modeColor = sys.mode === 'BUILD' ? C.green : sys.mode === 'CLOSURE' ? C.red : C.yellow;
    header.push(`MODE: ${modeColor}${sys.mode}${C.reset}  RISK: ${C.bold}${sys.openLoops > 10 ? 'HIGH' : sys.openLoops > 5 ? 'MEDIUM' : 'LOW'}${C.reset}  LOOPS: ${sys.openLoops}`);
  }

  if (!plan) {
    console.log(box('CYCLEBOARD', [...header, '', `${C.dim}No plan for today.${C.reset}`, `Run: cycleboard plan today A|B|C`]));
    return;
  }

  const pct = calcProgress(plan);
  const type = plan.day_type || '?';
  const tmpl = TEMPLATES[type];
  const lines: string[] = [
    ...header,
    '',
    `${C.bold}${type}-Day: ${tmpl?.name || 'Custom'}${C.reset}`,
    progressBar(pct),
    '',
    `${C.bold}TIME BLOCKS${C.reset}`,
  ];

  (plan.time_blocks || []).forEach((b: any, i: number) => {
    const check = b.completed ? `${C.green}[x]${C.reset}` : `${C.dim}[ ]${C.reset}`;
    const title = b.completed ? `${C.dim}${b.title}${C.reset}` : b.title;
    const time = (b.time || '').padEnd(8);
    lines.push(` ${String(i + 1).padStart(2)}. ${check} ${C.dim}${time}${C.reset} ${title}`);
  });

  lines.push('');
  lines.push(`${C.bold}GOALS${C.reset}`);
  if (plan.baseline_goal?.text) {
    const check = plan.baseline_goal.completed ? `${C.green}[x]${C.reset}` : `${C.dim}[ ]${C.reset}`;
    lines.push(` ${check} Baseline: ${plan.baseline_goal.text}`);
  }
  if (plan.stretch_goal?.text) {
    const check = plan.stretch_goal.completed ? `${C.green}[x]${C.reset}` : `${C.dim}[ ]${C.reset}`;
    lines.push(` ${check} Stretch:  ${plan.stretch_goal.text}`);
  }

  console.log(box('', lines, 55));
}

async function cmdCalendar(targetDate?: string) {
  const state = await fetchState();
  const today = todayISO();
  const ref = targetDate ? resolveDate(targetDate) : today;
  const [year, month] = ref.split('-').map(Number);
  const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];

  const firstDay = new Date(year, month - 1, 1);
  const daysInMonth = new Date(year, month, 0).getDate();
  const startDow = firstDay.getDay();

  const lines: string[] = [];
  lines.push(`${C.bold}       ${monthNames[month - 1]} ${year}${C.reset}`);
  lines.push(`${C.dim} Su  Mo  Tu  We  Th  Fr  Sa${C.reset}`);

  let row = '  '.repeat(startDow);
  for (let d = 1; d <= daysInMonth; d++) {
    const ds = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const plan = getDayPlan(state, ds);
    const pct = calcProgress(plan);
    const isToday = ds === today;
    const type = plan?.day_type || '';

    let cell: string;
    if (isToday) {
      cell = `${C.bold}${C.blue}[${String(d).padStart(2)}]${C.reset}`;
    } else if (plan && pct >= 70) {
      cell = `${C.green} ${String(d).padStart(2)}${C.reset} `;
    } else if (plan && pct >= 50) {
      cell = `${C.yellow} ${String(d).padStart(2)}${C.reset} `;
    } else if (plan) {
      cell = `${C.dim} ${String(d).padStart(2)}${C.reset} `;
    } else {
      cell = ` ${String(d).padStart(2)} `;
    }

    row += cell;
    if ((startDow + d) % 7 === 0 || d === daysInMonth) {
      lines.push(row);
      // Show day types below the row
      let typeRow = '  '.repeat(d === daysInMonth ? startDow : 0);
      const rowStart = d - ((startDow + d - 1) % 7);
      let hasTypes = false;
      for (let rd = Math.max(1, rowStart); rd <= d; rd++) {
        const rds = `${year}-${String(month).padStart(2, '0')}-${String(rd).padStart(2, '0')}`;
        const rp = getDayPlan(state, rds);
        if (rp?.day_type) {
          const tc = rp.day_type === 'A' ? C.blue : rp.day_type === 'B' ? C.yellow : C.red;
          typeRow += ` ${tc}${rp.day_type}${C.reset}  `;
          hasTypes = true;
        } else {
          typeRow += '    ';
        }
      }
      if (hasTypes) lines.push(typeRow);
      row = '';
    }
  }

  lines.push('');
  lines.push(`${C.dim}${C.green}■${C.reset}${C.dim}=70%+ ${C.yellow}■${C.reset}${C.dim}=50%+ ${C.blue}[n]${C.reset}${C.dim}=today${C.reset}`);

  console.log(lines.join('\n'));
}

async function cmdWeek(targetDate?: string) {
  const state = await fetchState();
  const today = todayISO();
  const ref = targetDate ? resolveDate(targetDate) : today;
  const d = new Date(ref + 'T12:00:00');
  const weekStart = new Date(d);
  weekStart.setDate(d.getDate() - d.getDay());

  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  console.log(`${C.bold}Week of ${formatDate(weekStart.toISOString().slice(0, 10))}${C.reset}\n`);

  for (let i = 0; i < 7; i++) {
    const wd = new Date(weekStart);
    wd.setDate(weekStart.getDate() + i);
    const ds = wd.toISOString().slice(0, 10);
    const plan = getDayPlan(state, ds);
    const pct = calcProgress(plan);
    const isToday = ds === today;
    const prefix = isToday ? `${C.blue}>${C.reset}` : ' ';
    const dayLabel = `${dayNames[i]} ${String(wd.getDate()).padStart(2)}`;

    if (!plan) {
      console.log(`${prefix} ${C.dim}${dayLabel}  --  no plan${C.reset}`);
    } else {
      const blocks = plan.time_blocks || [];
      const done = blocks.filter((b: any) => b.completed).length;
      const type = plan.day_type || '?';
      const tc = type === 'A' ? C.blue : type === 'B' ? C.yellow : C.red;
      const bar = progressBar(pct, 15);
      console.log(`${prefix} ${C.bold}${dayLabel}${C.reset}  ${tc}${type}${C.reset}  ${bar}  ${C.dim}${done}/${blocks.length} blocks${C.reset}`);
    }
  }
  console.log('');
}

async function cmdPlan(dateArg: string, typeArg: string) {
  const date = resolveDate(dateArg);
  const type = typeArg.toUpperCase();
  if (!TEMPLATES[type]) {
    console.error(`${C.red}Invalid type: ${typeArg}. Use A, B, or C.${C.reset}`);
    process.exit(1);
  }

  const state = await fetchState() || getDefaultState();
  if (!state.DayPlans) state.DayPlans = {};

  if (state.DayPlans[date]) {
    console.error(`${C.yellow}Plan already exists for ${formatDate(date)}. Use 'complete' to modify it.${C.reset}`);
    process.exit(1);
  }

  const tmpl = TEMPLATES[type];
  state.DayPlans[date] = {
    id: genId(),
    date,
    day_type: type,
    time_blocks: tmpl.blocks.map(b => ({ id: genId(), time: b.time, title: b.title, completed: false })),
    baseline_goal: { text: tmpl.baseline, completed: false },
    stretch_goal: { text: tmpl.stretch, completed: false },
    focus_areas: [],
    routines_completed: {},
    notes: '',
    rating: 0,
    progress_snapshots: [],
    final_progress: 0,
  };

  await saveState(state);
  console.log(`${C.green}✓${C.reset} Created ${C.bold}${type}-Day${C.reset} plan for ${formatDate(date)}`);
  console.log(`  ${tmpl.blocks.length} time blocks · Baseline: ${tmpl.baseline}`);
}

async function cmdComplete(indexStr: string, dateArg?: string) {
  const date = dateArg ? resolveDate(dateArg) : todayISO();
  const index = parseInt(indexStr, 10);
  if (isNaN(index) || index < 1) {
    console.error(`${C.red}Invalid block number: ${indexStr}${C.reset}`);
    process.exit(1);
  }

  const state = await fetchState();
  const plan = getDayPlan(state, date);
  if (!plan) {
    console.error(`${C.red}No plan for ${formatDate(date)}.${C.reset}`);
    process.exit(1);
  }

  const blocks = plan.time_blocks || [];
  if (index > blocks.length) {
    console.error(`${C.red}Only ${blocks.length} blocks. Index ${index} out of range.${C.reset}`);
    process.exit(1);
  }

  const block = blocks[index - 1];
  block.completed = !block.completed;
  await saveState(state);

  const status = block.completed ? `${C.green}✓ Completed${C.reset}` : `${C.yellow}○ Uncompleted${C.reset}`;
  console.log(`${status}: ${block.title} (${block.time})`);
  console.log(`  Progress: ${calcProgress(plan)}%`);
}

async function cmdAdd(dateArg: string, time: string, ...titleParts: string[]) {
  const date = resolveDate(dateArg);
  const title = titleParts.join(' ');
  if (!title) {
    console.error(`${C.red}Usage: cycleboard add <date> <time> <title>${C.reset}`);
    process.exit(1);
  }

  const state = await fetchState();
  const plan = getDayPlan(state, date);
  if (!plan) {
    console.error(`${C.red}No plan for ${formatDate(date)}. Create one first: cycleboard plan ${date} A|B|C${C.reset}`);
    process.exit(1);
  }

  plan.time_blocks.push({ id: genId(), time, title, completed: false });
  plan.time_blocks.sort((a: any, b: any) => (a.time || '').localeCompare(b.time || ''));
  await saveState(state);

  console.log(`${C.green}✓${C.reset} Added "${title}" at ${time} on ${formatDate(date)}`);
}

async function cmdStatus() {
  const sys = await fetchSystemState();
  const state = await fetchState();
  const today = todayISO();
  const plan = getDayPlan(state, today);
  const pct = calcProgress(plan);

  const lines: string[] = [];
  if (sys) {
    const modeColor = sys.mode === 'BUILD' ? C.green : sys.mode === 'CLOSURE' ? C.red : C.yellow;
    lines.push(`Mode:     ${modeColor}${C.bold}${sys.mode}${C.reset}`);
    lines.push(`Risk:     ${sys.openLoops > 10 ? C.red : C.green}${sys.openLoops > 10 ? 'HIGH' : sys.openLoops > 5 ? 'MEDIUM' : 'LOW'}${C.reset}`);
    lines.push(`Loops:    ${sys.openLoops}`);
    lines.push(`Streak:   ${sys.streakDays}d`);
  } else {
    lines.push(`${C.dim}System state unavailable${C.reset}`);
  }
  lines.push('');
  lines.push(`Today:    ${plan ? `${plan.day_type}-Day  ${pct}%` : 'No plan'}`);

  const planCount = state?.DayPlans ? Object.keys(state.DayPlans).length : 0;
  const taskCount = state?.AZTask ? state.AZTask.length : 0;
  const doneCount = state?.AZTask ? state.AZTask.filter((t: any) => t.status === 'Completed').length : 0;
  lines.push(`Plans:    ${planCount} days planned`);
  lines.push(`A-Z:      ${doneCount}/${taskCount} tasks done`);

  console.log(box('SYSTEM STATUS', lines, 45));
}

function getDefaultState(): any {
  return { version: '2.0', screen: 'Home', AZTask: [], DayPlans: {}, FocusArea: [], Routine: {}, DayTypeTemplates: {}, Settings: { darkMode: true, notifications: true, autoSave: true, defaultDayType: 'A' }, History: { completedTasks: [], productivityScore: 0, streak: 0, timeline: [] }, Journal: [], EightSteps: {}, Contingencies: {}, Reflections: { weekly: [], monthly: [], quarterly: [], yearly: [] }, MomentumWins: [], calendarView: 'month', calendarDate: todayISO() };
}

function showHelp() {
  console.log(`
${C.bold}${C.cyan}CycleBoard CLI${C.reset}

${C.bold}Usage:${C.reset} cycleboard <command> [args]

${C.bold}Commands:${C.reset}
  today                      Show today's plan
  calendar [date]            Month grid (defaults to current month)
  week [date]                Week overview
  plan <date> <A|B|C>        Create a day plan
  complete <n> [date]        Toggle time block N (defaults to today)
  add <date> <time> <title>  Add custom event
  status                     System overview
  help                       Show this help

${C.bold}Date formats:${C.reset}
  today, tomorrow, YYYY-MM-DD

${C.bold}Examples:${C.reset}
  cycleboard today
  cycleboard plan tomorrow A
  cycleboard complete 3
  cycleboard add 2026-04-10 14:00 Team Meeting
  cycleboard calendar 2026-05-01
`);
}

// === Dispatch ===

const args = process.argv.slice(2);
const cmd = args[0] || 'help';

switch (cmd) {
  case 'today': cmdToday(); break;
  case 'calendar': case 'cal': cmdCalendar(args[1]); break;
  case 'week': cmdWeek(args[1]); break;
  case 'plan': cmdPlan(args[1], args[2]); break;
  case 'complete': case 'done': cmdComplete(args[1], args[2]); break;
  case 'add': cmdAdd(args[1], args[2], ...args.slice(3)); break;
  case 'status': cmdStatus(); break;
  case 'help': case '--help': case '-h': showHelp(); break;
  default:
    console.error(`${C.red}Unknown command: ${cmd}${C.reset}`);
    showHelp();
    process.exit(1);
}
