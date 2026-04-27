#!/usr/bin/env tsx
/**
 * inPACT CLI — Personal productivity from the terminal.
 * Reads/writes the same CycleBoard state as the inPACT SPA via delta-kernel API.
 * No external dependencies beyond Node built-ins.
 */

const API = 'http://localhost:3001';

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

function box(title: string, lines: string[]) {
  const w = 56;
  const bar = '\u2500'.repeat(w);
  console.log(`\u2554\u2550${bold(title.padEnd(w))}\u2550\u2557`);
  for (const line of lines) {
    if (line === '---') {
      console.log(`\u255F\u2500${bar}\u2500\u2562`);
    } else {
      console.log(`\u2551 ${line.padEnd(w)} \u2551`);
    }
  }
  console.log(`\u255A\u2550${'\u2550'.repeat(w)}\u2550\u255D`);
}

function progressBar(pct: number, width = 20): string {
  const filled = Math.round((pct / 100) * width);
  const empty = width - filled;
  const color = pct >= 70 ? green : pct >= 50 ? yellow : dim;
  return color('\u2588'.repeat(filled) + '\u2591'.repeat(empty)) + ` ${pct}%`;
}

// ── Utilities ──

function todayDate(): string {
  return new Date().toISOString().slice(0, 10);
}

function generateId(): string {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
}

function parseFlag(args: string[], flag: string): string | null {
  const idx = args.indexOf(`--${flag}`);
  if (idx === -1 || idx + 1 >= args.length) return null;
  return args[idx + 1];
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

// ── State helpers ──

async function getCycleboardState(): Promise<any> {
  const res = await apiFetch('/api/cycleboard');
  // API returns { ok, data: { data: { ...state } } }
  return res?.data?.data || res?.data || {};
}

async function updateCycleboardState(updates: Record<string, any>): Promise<void> {
  const current = await getCycleboardState();
  const merged = { ...current, ...updates };
  await apiFetch('/api/cycleboard', { method: 'PUT', body: JSON.stringify(merged) });
}

// ── Home ──

async function showHome() {
  const state = await getCycleboardState().catch(() => ({}));
  const today = todayDate();

  // Try to get Atlas governance context
  let unified: any = null;
  try { unified = await apiFetch('/api/state/unified'); } catch {}

  const mode = unified?.derived?.mode || '--';
  const risk = unified?.derived?.open_loops > 10 ? 'HIGH' : unified?.derived?.open_loops > 5 ? 'MEDIUM' : 'LOW';
  const loops = unified?.derived?.open_loops ?? '--';
  const rawDirective = unified?.cognitive?.today?.directive || unified?.derived?.primary_order || '--';
  const directive = typeof rawDirective === 'string' ? rawDirective : rawDirective?.text || rawDirective?.title || '--';
  const streak = unified?.derived?.streak_days ?? 0;

  // Today's plan
  const plan = state?.DayPlans?.[today];
  const blocks = plan?.time_blocks || [];
  const blocksDone = blocks.filter((b: any) => b.completed).length;
  const dayPct = blocks.length ? Math.round((blocksDone / blocks.length) * 100) : 0;
  const dayType = plan?.day_type || '--';

  // Today fields
  const todayData = state?.Today?.daily?.[today] || {};

  // A-Z summary
  const azTasks = state?.AZTask || [];
  const azDone = azTasks.filter((t: any) => t.status === 'Completed').length;
  const azActive = azTasks.filter((t: any) => t.status === 'In Progress').length;
  const azPct = azTasks.length ? Math.round((azDone / azTasks.length) * 100) : 0;

  // Wins today
  const wins = (state?.MomentumWins || []).filter((w: any) => w.date === today).length;

  // Mission/motto
  const mission = state?.Today?.mission || '';
  const motto = state?.Today?.motto || '';

  const dateStr = new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });

  const lines: string[] = [];
  if (mission) lines.push(`${bold('Mission:')} ${mission}`);
  if (motto) lines.push(`${bold('Motto:')} ${motto}`);
  if (mission || motto) lines.push('---');

  if (todayData.winTarget) lines.push(`${bold('Win Target:')} ${todayData.winTarget}`);
  if (todayData.p1) lines.push(`${bold('P1:')} ${todayData.p1}`);
  if (todayData.p2) lines.push(`${bold('P2:')} ${todayData.p2}`);
  if (todayData.p3) lines.push(`${bold('P3:')} ${todayData.p3}`);
  if (todayData.lever) lines.push(`${bold('Lever:')} ${todayData.lever}`);
  if (todayData.winTarget || todayData.p1) lines.push('---');

  lines.push(
    `${bold('Today:')} ${dayType}-Day  ${plan ? progressBar(dayPct, 15) : dim('no plan')}  ${dim(blocksDone + '/' + blocks.length + ' blocks')}`,
    `${bold('A-Z:')} ${azDone}/${azTasks.length} (${azPct}%)   ${bold('Active:')} ${azActive}   ${bold('Wins:')} ${wins} today`,
  );

  // Atlas governance
  if (unified) {
    lines.push('---');
    lines.push(`${bold('Atlas:')} ${modeColor(mode)}   ${bold('Risk:')} ${risk === 'HIGH' ? red(risk) : risk === 'MEDIUM' ? yellow(risk) : green(risk)}   ${bold('Loops:')} ${loops}   ${bold('Streak:')} ${streak}d`);
    if (directive !== '--') lines.push(`${bold('Directive:')} ${String(directive).slice(0, 52)}`);
  }

  // In-progress tasks
  const active = azTasks.filter((t: any) => t.status === 'In Progress').slice(0, 5);
  if (active.length) {
    lines.push('---');
    lines.push(bold('In Progress:'));
    for (const t of active) {
      lines.push(`  ${bold(t.letter || '?')}  ${t.task || '--'}`);
    }
  }

  // Routine summary
  const routines = state?.Routine || {};
  const routineNames = Object.keys(routines);
  if (routineNames.length && plan) {
    const completed = plan.routines_completed || {};
    const parts = routineNames.map(name => {
      const steps = routines[name] || [];
      const rc = completed[name] || { steps: {} };
      const done = Object.values(rc.steps || {}).filter(Boolean).length;
      return `${name} ${done}/${steps.length}`;
    });
    lines.push('---');
    lines.push(`${bold('Routines:')} ${parts.join('  ')}`);
  }

  box(`inPACT HOME \u00b7 ${dateStr}`, lines);
}

// ── Day Plan commands ──

async function showDay(args: string[]) {
  const date = args[0] || todayDate();
  const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan) {
    console.log(yellow(`No plan for ${date}.`));
    console.log(dim(`Create one: inpact day create [A|B|C]`));
    return;
  }
  box(`DAY PLAN \u00b7 ${date}`, [
    `${bold('Type:')} ${cyan(plan.day_type || '--')}-Day`,
    `${bold('Baseline:')} ${plan.baseline_goal?.text || '--'} ${plan.baseline_goal?.completed ? green('[DONE]') : ''}`,
    `${bold('Stretch:')}  ${plan.stretch_goal?.text || '--'} ${plan.stretch_goal?.completed ? green('[DONE]') : ''}`,
    '---',
    bold('Time Blocks:'),
    ...(plan.time_blocks || []).map((b: any, i: number) =>
      `  ${dim(String(i + 1).padStart(2) + '.')} ${dim(b.time || '--')} ${b.completed ? green('\u2713') : '\u25CB'} ${b.title || 'Untitled'}`
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
  if (state.DayPlans[date]) { console.log(yellow(`Plan already exists for ${date}. Use: inpact day`)); return; }

  // Pull from DayTypeTemplates if available
  const template = state.DayTypeTemplates?.[dayType];
  const timeBlocks = template?.timeBlocks?.map((b: any) => ({
    id: generateId(),
    time: b.time || '',
    title: b.title || '',
    completed: false,
  })) || [];
  const goals = template?.goals || {};

  state.DayPlans[date] = {
    id: generateId(),
    date,
    day_type: dayType,
    time_blocks: timeBlocks,
    baseline_goal: { text: goals.baseline || '', completed: false },
    stretch_goal: { text: goals.stretch || '', completed: false },
    focus_areas: [],
    routines_completed: {},
    notes: '',
    rating: 0,
    progress_snapshots: [],
    final_progress: 0,
  };
  await updateCycleboardState({ DayPlans: state.DayPlans });
  console.log(green(`Created ${dayType}-Day plan for ${date} (${timeBlocks.length} blocks from template)`));
}

async function addBlock(args: string[]) {
  const time = args[0];
  const title = args.slice(1).join(' ');
  if (!time || !title) { console.log(red('Usage: inpact day block <time> <title>')); return; }
  const date = todayDate();
  const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan) { console.log(red(`No plan for today. Run: inpact day create A`)); return; }
  plan.time_blocks.push({ id: generateId(), time, title, completed: false });
  plan.time_blocks.sort((a: any, b: any) => (a.time || '').localeCompare(b.time || ''));
  await updateCycleboardState({ DayPlans: state.DayPlans });
  console.log(green(`Added "${title}" at ${time}`));
}

async function completeBlock(args: string[]) {
  const idx = parseInt(args[0]) - 1;
  if (isNaN(idx)) { console.log(red('Usage: inpact day done <block#> (1-based)')); return; }
  const date = todayDate();
  const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan || !plan.time_blocks[idx]) { console.log(red('Block not found')); return; }
  plan.time_blocks[idx].completed = true;
  await updateCycleboardState({ DayPlans: state.DayPlans });
  console.log(green(`Completed: ${plan.time_blocks[idx].title}`));
}

async function removeBlock(args: string[]) {
  const idx = parseInt(args[0]) - 1;
  if (isNaN(idx)) { console.log(red('Usage: inpact day remove <block#> (1-based)')); return; }
  const date = todayDate();
  const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan || !plan.time_blocks[idx]) { console.log(red('Block not found')); return; }
  const removed = plan.time_blocks.splice(idx, 1)[0];
  await updateCycleboardState({ DayPlans: state.DayPlans });
  console.log(green(`Removed: ${removed.title}`));
}

async function setGoal(args: string[]) {
  const type = args[0];
  const text = args.slice(1).join(' ');
  if (!type || !text || !['baseline', 'stretch'].includes(type)) {
    console.log(red('Usage: inpact day goal baseline|stretch <text>')); return;
  }
  const date = todayDate();
  const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan) { console.log(red('No plan for today.')); return; }
  plan[`${type}_goal`] = { text, completed: false };
  await updateCycleboardState({ DayPlans: state.DayPlans });
  console.log(green(`Set ${type} goal: ${text}`));
}

async function completeGoal(args: string[]) {
  const type = args[0];
  if (!type || !['baseline', 'stretch'].includes(type)) {
    console.log(red('Usage: inpact day goal-done baseline|stretch')); return;
  }
  const date = todayDate();
  const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan) { console.log(red('No plan for today.')); return; }
  const key = `${type}_goal`;
  if (!plan[key]) { console.log(red(`No ${type} goal set.`)); return; }
  plan[key].completed = true;
  await updateCycleboardState({ DayPlans: state.DayPlans });
  console.log(green(`${type} goal completed!`));
}

async function rateDay(args: string[]) {
  const rating = parseInt(args[0]);
  if (isNaN(rating) || rating < 1 || rating > 5) { console.log(red('Usage: inpact day rate <1-5>')); return; }
  const date = todayDate();
  const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan) { console.log(red('No plan for today.')); return; }
  plan.rating = rating;
  await updateCycleboardState({ DayPlans: state.DayPlans });
  console.log(green(`Rated today: ${rating}/5`));
}

async function setDayNote(args: string[]) {
  const text = args.join(' ');
  if (!text) { console.log(red('Usage: inpact day note <text>')); return; }
  const date = todayDate();
  const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan) { console.log(red('No plan for today.')); return; }
  plan.notes = text;
  await updateCycleboardState({ DayPlans: state.DayPlans });
  console.log(green('Day note set.'));
}

async function dayCmd(args: string[]) {
  const sub = args[0];
  if (!sub || sub.match(/^\d{4}-\d{2}-\d{2}$/)) return showDay(args);
  if (sub === 'create') return createDay(args.slice(1));
  if (sub === 'block') return addBlock(args.slice(1));
  if (sub === 'done') return completeBlock(args.slice(1));
  if (sub === 'remove') return removeBlock(args.slice(1));
  if (sub === 'goal') return setGoal(args.slice(1));
  if (sub === 'goal-done') return completeGoal(args.slice(1));
  if (sub === 'rate') return rateDay(args.slice(1));
  if (sub === 'note') return setDayNote(args.slice(1));
  console.log('Usage: inpact day [date] | create A|B|C | block <time> <title> | done <#> | remove <#> | goal baseline|stretch <text> | goal-done baseline|stretch | rate <1-5> | note <text>');
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
      console.log(`    ${isDone ? green('\u2713') : '\u25CB'} ${dim(String(i + 1).padStart(2) + '.')} ${typeof step === 'string' ? step : step.name || step.title || 'Step ' + (i + 1)}`);
    });
  }
}

async function completeRoutineStep(args: string[]) {
  const routineName = args[0];
  const stepIdx = parseInt(args[1]) - 1;
  if (!routineName || isNaN(stepIdx)) { console.log(red('Usage: inpact routine done <name> <step#>')); return; }
  const date = todayDate();
  const state = await getCycleboardState();
  const plan = state?.DayPlans?.[date];
  if (!plan) { console.log(red('No day plan. Create one first: inpact day create A')); return; }
  if (!plan.routines_completed) plan.routines_completed = {};
  if (!plan.routines_completed[routineName]) plan.routines_completed[routineName] = { completed: false, steps: {} };
  plan.routines_completed[routineName].steps[stepIdx] = true;
  const routine = state.Routine?.[routineName] || [];
  const allDone = routine.every((_: any, i: number) => plan.routines_completed[routineName].steps[i]);
  if (allDone) plan.routines_completed[routineName].completed = true;
  await updateCycleboardState({ DayPlans: state.DayPlans });
  console.log(green(`${routineName} step ${stepIdx + 1} done${allDone ? ' \u2014 routine complete!' : ''}`));
}

async function routineCmd(args: string[]) {
  if (!args[0] || args[0] === 'list') return showRoutines();
  if (args[0] === 'done') return completeRoutineStep(args.slice(1));
  console.log('Usage: inpact routine [list] | done <name> <step#>');
}

// ── A-Z Task commands ──

async function showTasks(args: string[]) {
  const state = await getCycleboardState();
  const tasks = state?.AZTask || [];
  const filter = parseFlag(args, 'status');
  const search = parseFlag(args, 'search');

  let filtered = tasks;
  if (filter === 'completed') filtered = tasks.filter((t: any) => t.status === 'Completed');
  else if (filter === 'in-progress') filtered = tasks.filter((t: any) => t.status === 'In Progress');
  else if (filter === 'not-started') filtered = tasks.filter((t: any) => !t.status || t.status === 'Not Started');
  if (search) filtered = filtered.filter((t: any) => (t.task || '').toLowerCase().includes(search.toLowerCase()));

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
    const grouped: Record<string, any[]> = {};
    for (const t of filtered) {
      const letter = (t.letter || '?').toUpperCase();
      if (!grouped[letter]) grouped[letter] = [];
      grouped[letter].push(t);
    }
    const sortedLetters = Object.keys(grouped).sort();
    for (const letter of sortedLetters) {
      for (const t of grouped[letter]) {
        const icon = t.status === 'Completed' ? green('\u2713') : t.status === 'In Progress' ? yellow('\u25B8') : '\u25CB';
        const task = t.status === 'Completed' ? dim(t.task || '--') : (t.task || '--');
        const notes = t.notes ? dim(` (${t.notes.slice(0, 25)})`) : '';
        lines.push(`  ${bold(letter)}  ${icon}  ${task}${notes}`);
      }
    }
  }

  box('A-Z TASKS', lines);
}

async function addTask(args: string[]) {
  const letter = args[0]?.toUpperCase();
  const task = args.slice(1).join(' ');
  if (!letter || !task || letter.length !== 1) { console.log(red('Usage: inpact task add <letter> <task>')); return; }
  const state = await getCycleboardState();
  if (!state.AZTask) state.AZTask = [];
  state.AZTask.push({
    id: generateId(),
    letter,
    task,
    status: 'Not Started',
    notes: '',
    createdAt: new Date().toISOString(),
  });
  await updateCycleboardState({ AZTask: state.AZTask });
  console.log(green(`Added ${letter}: ${task}`));
}

async function toggleTask(args: string[], targetStatus: string) {
  const query = args[0];
  if (!query) { console.log(red(`Usage: inpact task ${targetStatus === 'Completed' ? 'done' : 'start'} <letter-or-id>`)); return; }
  const state = await getCycleboardState();
  const tasks = state?.AZTask || [];
  const match = tasks.find((t: any) =>
    t.id === query || (t.letter || '').toUpperCase() === query.toUpperCase()
  );
  if (!match) { console.log(red(`No A-Z task matching "${query}"`)); return; }
  match.status = targetStatus;
  if (targetStatus === 'Completed') {
    // Record in history
    if (!state.History) state.History = { completedTasks: [], streak: 0, timeline: [] };
    state.History.completedTasks.push({
      letter: match.letter,
      task: match.task,
      completedAt: new Date().toISOString(),
    });
    await updateCycleboardState({ AZTask: tasks, History: state.History });
  } else {
    await updateCycleboardState({ AZTask: tasks });
  }
  console.log(green(`${match.letter}: ${match.task} \u2192 ${targetStatus}`));
}

async function deleteTask(args: string[]) {
  const query = args[0];
  if (!query) { console.log(red('Usage: inpact task delete <letter-or-id>')); return; }
  const state = await getCycleboardState();
  const tasks = state?.AZTask || [];
  const idx = tasks.findIndex((t: any) =>
    t.id === query || (t.letter || '').toUpperCase() === query.toUpperCase()
  );
  if (idx === -1) { console.log(red(`No A-Z task matching "${query}"`)); return; }
  const removed = tasks.splice(idx, 1)[0];
  await updateCycleboardState({ AZTask: tasks });
  console.log(green(`Deleted ${removed.letter}: ${removed.task}`));
}

async function taskCmd(args: string[]) {
  if (!args[0]) { console.log('Usage: inpact task add|done|start|delete <args>'); return; }
  if (args[0] === 'add') return addTask(args.slice(1));
  if (args[0] === 'done') return toggleTask(args.slice(1), 'Completed');
  if (args[0] === 'start') return toggleTask(args.slice(1), 'In Progress');
  if (args[0] === 'delete') return deleteTask(args.slice(1));
  console.log('Usage: inpact task add <letter> <task> | done <letter> | start <letter> | delete <letter>');
}

// ── Focus Areas ──

async function showFocusAreas() {
  const state = await getCycleboardState();
  const areas = state?.FocusArea || [];
  if (areas.length === 0) { console.log(dim('No focus areas defined.')); return; }
  console.log(bold('Focus Areas:'));
  for (const area of areas) {
    const tasks = area.tasks || [];
    const done = tasks.filter((t: any) => t.completed || t.status === 'Completed').length;
    console.log(`\n  ${bold(area.name || 'Untitled')} ${dim(`(${done}/${tasks.length})`)} ${dim(area.definition || '')}`);
    for (const [i, t] of tasks.entries()) {
      console.log(`    ${t.completed || t.status === 'Completed' ? green('\u2713') : '\u25CB'} ${dim(String(i + 1) + '.')} ${t.text || t.task || '--'}`);
    }
    if (tasks.length === 0) console.log(dim('    (no tasks)'));
  }
}

async function addFocusTask(args: string[]) {
  const areaName = args[0];
  const text = args.slice(1).join(' ');
  if (!areaName || !text) { console.log(red('Usage: inpact focus add <area-name> <task-text>')); return; }
  const state = await getCycleboardState();
  const areas = state?.FocusArea || [];
  const area = areas.find((a: any) => (a.name || '').toLowerCase() === areaName.toLowerCase());
  if (!area) { console.log(red(`Focus area "${areaName}" not found. Areas: ${areas.map((a: any) => a.name).join(', ')}`)); return; }
  if (!area.tasks) area.tasks = [];
  area.tasks.push({ id: generateId(), text, completed: false });
  await updateCycleboardState({ FocusArea: areas });
  console.log(green(`Added to ${area.name}: ${text}`));
}

async function toggleFocusTask(args: string[]) {
  const areaName = args[0];
  const idx = parseInt(args[1]) - 1;
  if (!areaName || isNaN(idx)) { console.log(red('Usage: inpact focus done <area-name> <task#>')); return; }
  const state = await getCycleboardState();
  const areas = state?.FocusArea || [];
  const area = areas.find((a: any) => (a.name || '').toLowerCase() === areaName.toLowerCase());
  if (!area || !area.tasks?.[idx]) { console.log(red(`Task not found in "${areaName}"`)); return; }
  area.tasks[idx].completed = !area.tasks[idx].completed;
  await updateCycleboardState({ FocusArea: areas });
  const t = area.tasks[idx];
  console.log(green(`${t.completed ? 'Completed' : 'Uncompleted'}: ${t.text}`));
}

async function focusCmd(args: string[]) {
  if (!args[0] || args[0] === 'list') return showFocusAreas();
  if (args[0] === 'add') return addFocusTask(args.slice(1));
  if (args[0] === 'done') return toggleFocusTask(args.slice(1));
  console.log('Usage: inpact focus [list] | add <area> <text> | done <area> <task#>');
}

// ── Weekly Plan ──

async function showWeekly() {
  const state = await getCycleboardState();
  const wp = state?.WeeklyPlan || {};
  const focus = state?.FocusArea || [];

  const lines: string[] = [];
  if (wp.weekOf) lines.push(`${bold('Week of:')} ${wp.weekOf}`);
  if (wp.primaryLetter) lines.push(`${bold('Primary Letter:')} ${cyan(wp.primaryLetter)}`);
  if (wp.weekCountsIf) lines.push(`${bold('Week Counts If:')} ${wp.weekCountsIf}`);
  if (wp.pigpenFocus && Object.keys(wp.pigpenFocus).length) {
    lines.push(`${bold('PIGPEN Focus:')} ${Object.entries(wp.pigpenFocus).map(([k, v]) => `${k}=${v}`).join(', ')}`);
  }
  if (wp.closed) lines.push(green('Week closed'));

  if (lines.length === 0) {
    console.log(dim('No weekly plan set.'));
    return;
  }

  // Focus area summary
  if (focus.length) {
    lines.push('---');
    lines.push(bold('Focus Areas:'));
    for (const area of focus) {
      const tasks = area.tasks || [];
      const done = tasks.filter((t: any) => t.completed || t.status === 'Completed').length;
      lines.push(`  ${bold(area.name || 'Untitled')} ${dim(`${done}/${tasks.length}`)}`);
    }
  }

  box('WEEKLY PLAN', lines);
}

// ── Journal ──

async function showJournal(args: string[]) {
  const state = await getCycleboardState();
  const entries = state?.Journal || [];
  const count = parseInt(args[0]) || 5;
  const recent = entries.slice(-count).reverse();
  if (recent.length === 0) { console.log(dim('No journal entries. Add one: inpact journal add <text>')); return; }
  console.log(bold('Journal:'));
  for (const entry of recent) {
    const date = entry.date || entry.createdAt?.slice(0, 10) || '--';
    console.log(`\n  ${dim(date)} ${entry.mood ? `[${entry.mood}]` : ''}`);
    if (entry.title) console.log(`  ${bold(entry.title)}`);
    console.log(`  ${entry.content || entry.text || '--'}`);
  }
}

async function addJournal(args: string[]) {
  const text = args.join(' ');
  if (!text) { console.log(red('Usage: inpact journal add <entry text>')); return; }
  const state = await getCycleboardState();
  if (!state.Journal) state.Journal = [];
  state.Journal.push({
    id: generateId(),
    date: todayDate(),
    createdAt: new Date().toISOString(),
    content: text,
    mood: null,
  });
  await updateCycleboardState({ Journal: state.Journal });
  console.log(green('Journal entry added.'));
}

async function journalCmd(args: string[]) {
  if (!args[0] || args[0] === 'list' || !isNaN(parseInt(args[0]))) return showJournal(args);
  if (args[0] === 'add') return addJournal(args.slice(1));
  console.log('Usage: inpact journal [count] | add <text>');
}

// ── Momentum Wins ──

async function showWins() {
  const state = await getCycleboardState();
  const wins = state?.MomentumWins || [];
  const todayWins = wins.filter((w: any) => w.date === todayDate());
  const recent = wins.slice(-5).reverse();
  console.log(bold(`Momentum Wins`) + ` \u00b7 ${todayWins.length} today, ${wins.length} total`);
  if (recent.length === 0) { console.log(dim('  No wins yet. Log one: inpact win <description>')); return; }
  for (const w of recent) {
    console.log(`  ${dim(w.date || '--')} ${green('\u2605')} ${w.description || w.text || '--'}`);
  }
}

async function addWin(args: string[]) {
  const text = args.join(' ');
  if (!text) { console.log(red('Usage: inpact win <description>')); return; }
  const state = await getCycleboardState();
  if (!state.MomentumWins) state.MomentumWins = [];
  state.MomentumWins.push({
    id: generateId(),
    date: todayDate(),
    timestamp: new Date().toISOString(),
    description: text,
  });
  await updateCycleboardState({ MomentumWins: state.MomentumWins });
  console.log(green(`Win logged: ${text}`));
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
    console.log(red('Usage: inpact reflect add weekly|monthly|quarterly|yearly <text>')); return;
  }
  const state = await getCycleboardState();
  if (!state.Reflections) state.Reflections = { weekly: [], monthly: [], quarterly: [], yearly: [] };
  if (!state.Reflections[type]) state.Reflections[type] = [];
  state.Reflections[type].push({
    id: generateId(),
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
  console.log('Usage: inpact reflect [weekly|monthly|quarterly|yearly] | add <type> <text>');
}

// ── Calendar ──

async function showCalendar(args: string[]) {
  const sub = args[0];
  if (sub === 'week') return showCalendarWeek(args[1]);
  return showCalendarMonth(args[0]);
}

async function showCalendarMonth(targetDate?: string) {
  const state = await getCycleboardState();
  const today = todayDate();
  const ref = targetDate && /^\d{4}-\d{2}(-\d{2})?$/.test(targetDate)
    ? (targetDate.length === 7 ? targetDate + '-01' : targetDate)
    : today;
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
  console.log(`${green('\u25A0')}${dim('=70%+')} ${yellow('\u25A0')}${dim('=50%+')} ${cyan('[n]')}${dim('=today')}`);

  const planned = Object.keys(state?.DayPlans || {}).filter(k => k.startsWith(`${year}-${String(month).padStart(2, '0')}`));
  if (planned.length) {
    const avgPct = Math.round(planned.reduce((sum: number, k: string) => {
      const p = state.DayPlans[k];
      const b = p?.time_blocks || [];
      const d = b.filter((x: any) => x.completed).length;
      return sum + (b.length ? (d / b.length) * 100 : 0);
    }, 0) / planned.length);
    console.log(dim(`  ${planned.length} days planned . avg ${avgPct}% complete`));
  }
}

async function showCalendarWeek(targetDate?: string) {
  const state = await getCycleboardState();
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

// ── Statistics ──

async function showStats() {
  const state = await getCycleboardState();
  let unified: any = null;
  try { unified = await apiFetch('/api/state/unified'); } catch {}

  const tasks = state?.AZTask || [];
  const completedTasks = tasks.filter((t: any) => t.status === 'Completed').length;
  const inProgressTasks = tasks.filter((t: any) => t.status === 'In Progress').length;
  const wins = state?.MomentumWins || [];
  const journalEntries = state?.Journal || [];
  const reflections = state?.Reflections || {};
  const totalReflections = Object.values(reflections).reduce((sum: number, arr: any) => sum + (arr?.length || 0), 0);

  // Day plan stats
  const dayPlans = state?.DayPlans || {};
  const planDates = Object.keys(dayPlans);
  let totalBlocksDone = 0;
  let totalBlocks = 0;
  let daysRated = 0;
  let ratingSum = 0;
  for (const d of planDates) {
    const p = dayPlans[d];
    const b = p?.time_blocks || [];
    totalBlocks += b.length;
    totalBlocksDone += b.filter((x: any) => x.completed).length;
    if (p?.rating > 0) { daysRated++; ratingSum += p.rating; }
  }
  const avgBlockPct = totalBlocks ? Math.round((totalBlocksDone / totalBlocks) * 100) : 0;
  const avgRating = daysRated ? (ratingSum / daysRated).toFixed(1) : '--';

  box('STATISTICS', [
    `${bold('A-Z Tasks:')} ${completedTasks}/${tasks.length} completed (${tasks.length ? Math.round(completedTasks / tasks.length * 100) : 0}%)`,
    `${bold('In Progress:')} ${inProgressTasks}`,
    `${bold('Momentum Wins:')} ${wins.length} total, ${wins.filter((w: any) => w.date === todayDate()).length} today`,
    `${bold('Journal Entries:')} ${journalEntries.length}`,
    `${bold('Reflections:')} ${totalReflections}`,
    '---',
    `${bold('Day Plans:')} ${planDates.length} days planned`,
    `${bold('Block Completion:')} ${totalBlocksDone}/${totalBlocks} (${avgBlockPct}%)`,
    `${bold('Avg Day Rating:')} ${avgRating}/5 (${daysRated} rated)`,
    '---',
    `${bold('Streak:')} ${unified?.derived?.streak_days ?? state?.History?.streak ?? 0} day(s)`,
    `${bold('Open Loops:')} ${unified?.derived?.open_loops ?? '--'}`,
    `${bold('Closure Ratio:')} ${unified?.derived?.closure_ratio != null ? (unified.derived.closure_ratio * 100).toFixed(1) + '%' : '--'}`,
  ]);
}

// ── Settings ──

async function showSettings() {
  const state = await getCycleboardState();
  const settings = state?.Settings || {};

  // Connection test
  let connected = false;
  try {
    const health = await apiFetch('/api/services/health');
    connected = !!health;
  } catch {}

  console.log(bold('Settings:'));
  for (const [key, value] of Object.entries(settings)) {
    console.log(`  ${key.padEnd(22)} ${String(value)}`);
  }
  console.log('');
  console.log(bold('Atlas Connection:'));
  console.log(`  Status:              ${connected ? green('Connected') : yellow('Offline')}`);
  console.log(`  API URL:             ${API}`);
}

async function updateSetting(args: string[]) {
  const key = args[0];
  const value = args.slice(1).join(' ');
  if (!key || !value) { console.log(red('Usage: inpact settings set <key> <value>')); return; }
  const state = await getCycleboardState();
  if (!state.Settings) state.Settings = {};
  // Parse booleans and numbers
  let parsed: any = value;
  if (value === 'true') parsed = true;
  else if (value === 'false') parsed = false;
  else if (!isNaN(Number(value))) parsed = Number(value);
  state.Settings[key] = parsed;
  await updateCycleboardState({ Settings: state.Settings });
  console.log(green(`Settings: ${key} = ${parsed}`));
}

async function testConnection() {
  try {
    const health = await apiFetch('/api/services/health');
    console.log(green('Connected to Atlas API'));
    if (health && typeof health === 'object') {
      for (const [name, info] of Object.entries(health) as [string, any][]) {
        const up = info?.status === 'up';
        console.log(`  ${up ? green('\u25CF') : red('\u25CF')} ${name}`);
      }
    }
  } catch (e: any) {
    console.log(red('Cannot reach Atlas API'));
    console.log(dim(e.message || 'Connection refused'));
  }
}

async function syncNow() {
  try {
    const state = await getCycleboardState();
    const keys = Object.keys(state);
    console.log(green('Synced with Atlas API'));
    console.log(dim(`  State keys: ${keys.length}`));
    console.log(dim(`  Size: ~${Math.round(JSON.stringify(state).length / 1024)}KB`));
  } catch (e: any) {
    console.log(red('Sync failed'));
    console.log(dim(e.message || 'Connection refused'));
  }
}

async function settingsCmd(args: string[]) {
  if (!args[0] || args[0] === 'list') return showSettings();
  if (args[0] === 'set') return updateSetting(args.slice(1));
  console.log('Usage: inpact settings [list] | set <key> <value>');
}

// ── Help ──

function showHelp() {
  console.log(bold('inPACT CLI') + ' \u00b7 Personal productivity from the terminal.\n');
  const cmds = [
    [dim('Overview'), ''],
    ['home', 'At-a-glance dashboard'],
    ['status', 'Alias for home'],
    ['', ''],
    [dim('Daily'), ''],
    ['day [date]', 'Show day plan'],
    ['day create A|B|C', 'Create today\'s plan from template'],
    ['day block <time> <title>', 'Add time block'],
    ['day done <block#>', 'Complete time block'],
    ['day remove <block#>', 'Remove time block'],
    ['day goal baseline|stretch <text>', 'Set daily goal'],
    ['day goal-done baseline|stretch', 'Mark goal completed'],
    ['day rate <1-5>', 'Rate the day'],
    ['day note <text>', 'Set daily notes'],
    ['routine', 'Show routines with completion'],
    ['routine done <name> <step#>', 'Complete routine step'],
    ['', ''],
    [dim('Tasks'), ''],
    ['tasks [--status --search]', 'List A-Z tasks'],
    ['task add <letter> <task>', 'Add A-Z task'],
    ['task start <letter>', 'Start a task'],
    ['task done <letter>', 'Complete a task'],
    ['task delete <letter>', 'Delete a task'],
    ['focus', 'Show focus areas'],
    ['focus add <area> <text>', 'Add focus area task'],
    ['focus done <area> <task#>', 'Toggle focus task'],
    ['weekly', 'Show weekly plan'],
    ['', ''],
    [dim('History'), ''],
    ['journal [count]', 'Show journal entries'],
    ['journal add <text>', 'Add journal entry'],
    ['win <description>', 'Log a momentum win'],
    ['wins', 'Show wins'],
    ['reflect [type]', 'Show reflections'],
    ['reflect add <type> <text>', 'Add reflection'],
    ['calendar [YYYY-MM]', 'Month calendar view'],
    ['calendar week [date]', 'Week calendar view'],
    ['stats', 'Statistics'],
    ['', ''],
    [dim('Settings'), ''],
    ['settings', 'Show settings + connection status'],
    ['settings set <key> <value>', 'Update a setting'],
    ['sync', 'Sync with Atlas API'],
    ['test-connection', 'Test API connectivity'],
    ['help', 'Show this help'],
  ];
  for (const [cmd, desc] of cmds) {
    if (!cmd) { console.log(''); continue; }
    console.log(`  ${cyan(cmd.padEnd(36))} ${desc}`);
  }
}

// ── Dispatcher ──

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];
  const rest = args.slice(1);

  switch (command) {
    // Home
    case 'home': case 'status': return showHome();
    // Daily
    case 'day': return dayCmd(rest);
    case 'routine': return routineCmd(rest);
    // Tasks
    case 'tasks': return showTasks(rest);
    case 'task': return taskCmd(rest);
    case 'focus': return focusCmd(rest);
    case 'weekly': return showWeekly();
    // History
    case 'journal': return journalCmd(rest);
    case 'win': return addWin(rest);
    case 'wins': return showWins();
    case 'reflect': return reflectCmd(rest);
    case 'calendar': case 'cal': return showCalendar(rest);
    case 'stats': return showStats();
    // Settings
    case 'settings': return settingsCmd(rest);
    case 'sync': return syncNow();
    case 'test-connection': return testConnection();
    // Meta
    case 'help':
    case undefined: return showHelp();
    default:
      console.log(red(`Unknown command: ${command}`) + '. Run ' + cyan('inpact help'));
      process.exit(1);
  }
}

main().catch(err => {
  console.error(red('Error:'), err.message || err);
  if (err.cause?.code === 'ECONNREFUSED') {
    console.error(yellow('Delta-kernel API is not running. Start it: npx tsx services/delta-kernel/src/api/server.ts'));
  }
  process.exit(1);
});
