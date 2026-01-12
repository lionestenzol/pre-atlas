/**
 * Delta-State Fabric — CLI Renderer
 *
 * Renders the cockpit shell to the terminal.
 * Text-based UI with box drawing characters.
 */

import { CockpitState } from '../core/cockpit';
import {
  Mode,
  TaskData,
  DraftData,
  ThreadData,
  Entity,
} from '../core/types';

// ANSI color codes
const COLORS = {
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
  bgBlue: '\x1b[44m',
  bgGreen: '\x1b[42m',
  bgYellow: '\x1b[43m',
  bgRed: '\x1b[41m',
  bgMagenta: '\x1b[45m',
};

// Mode colors
const MODE_COLORS: Record<Mode, string> = {
  RECOVER: COLORS.bgRed,
  CLOSE_LOOPS: COLORS.bgYellow,
  BUILD: COLORS.bgGreen,
  COMPOUND: COLORS.bgBlue,
  SCALE: COLORS.bgMagenta,
};

// Box drawing characters
const BOX = {
  topLeft: '┌',
  topRight: '┐',
  bottomLeft: '└',
  bottomRight: '┘',
  horizontal: '─',
  vertical: '│',
  teeLeft: '├',
  teeRight: '┤',
};

export interface RenderContext {
  cockpit: CockpitState;
  tasks: Array<{ entity: Entity; state: TaskData }>;
  drafts: Array<{ entity: Entity; state: DraftData }>;
  threads: Array<{ entity: Entity; state: ThreadData }>;
  selectedIndex: number;
  statusMessage: string;
  lastSync: Date | null;
}

export function clearScreen(): void {
  process.stdout.write('\x1b[2J\x1b[H');
}

export function renderCockpit(ctx: RenderContext): string {
  const lines: string[] = [];
  const width = 60;

  // Header
  lines.push(renderHeader(ctx.cockpit.mode, width));
  lines.push(renderDivider(width));

  // Actions section
  lines.push(renderSectionHeader('ACTIONS', width));
  const actions = buildActionList(ctx);
  for (let i = 0; i < actions.length; i++) {
    const selected = i === ctx.selectedIndex;
    lines.push(renderActionItem(i + 1, actions[i], selected, width));
  }

  if (actions.length === 0) {
    lines.push(renderEmptyLine('No actions available', width));
  }

  lines.push(renderDivider(width));

  // Tasks section
  lines.push(renderSectionHeader('TASKS', width));
  const activeTasks = ctx.tasks.filter(t => t.state.status !== 'DONE' && t.state.status !== 'ARCHIVED');
  for (const task of activeTasks.slice(0, 5)) {
    lines.push(renderTaskItem(task.state, width));
  }

  if (activeTasks.length === 0) {
    lines.push(renderEmptyLine('No active tasks', width));
  } else if (activeTasks.length > 5) {
    lines.push(renderEmptyLine(`... and ${activeTasks.length - 5} more`, width));
  }

  lines.push(renderDivider(width));

  // Leverage hint
  if (ctx.cockpit.leverage_hint) {
    lines.push(renderHint(ctx.cockpit.leverage_hint, width));
    lines.push(renderDivider(width));
  }

  // Status bar
  lines.push(renderStatusBar(ctx, width));

  // Footer
  lines.push(renderFooter(width));

  // Help line
  lines.push('');
  lines.push(`${COLORS.dim}[↑↓] Navigate  [Enter] Select  [n] New Task  [q] Quit${COLORS.reset}`);

  return lines.join('\n');
}

function renderHeader(mode: Mode, width: number): string {
  const modeColor = MODE_COLORS[mode];
  const modeText = ` MODE: ${mode} `;
  const padding = width - modeText.length - 2;
  const leftPad = Math.floor(padding / 2);
  const rightPad = padding - leftPad;

  return (
    BOX.topLeft +
    BOX.horizontal.repeat(leftPad) +
    `${modeColor}${COLORS.bold}${modeText}${COLORS.reset}` +
    BOX.horizontal.repeat(rightPad) +
    BOX.topRight
  );
}

function renderDivider(width: number): string {
  return BOX.teeLeft + BOX.horizontal.repeat(width - 2) + BOX.teeRight;
}

function renderSectionHeader(title: string, width: number): string {
  const text = ` ${title} `;
  const remaining = width - text.length - 2;
  return (
    BOX.vertical +
    `${COLORS.bold}${COLORS.cyan}${text}${COLORS.reset}` +
    ' '.repeat(remaining) +
    BOX.vertical
  );
}

function renderActionItem(
  index: number,
  action: ActionItem,
  selected: boolean,
  width: number
): string {
  const prefix = selected ? `${COLORS.bgBlue}${COLORS.white}` : '';
  const suffix = selected ? COLORS.reset : '';

  const indexStr = `[${index}]`;
  const label = truncate(action.label, width - 10);
  const content = `${indexStr} ${label}`;
  const padding = width - content.length - 2;

  return (
    BOX.vertical +
    prefix +
    ' ' +
    content +
    ' '.repeat(Math.max(0, padding - 1)) +
    suffix +
    BOX.vertical
  );
}

function renderTaskItem(task: TaskData, width: number): string {
  const priority = task.priority === 'HIGH' ? `${COLORS.red}!${COLORS.reset}` : ' ';
  const status = task.status === 'IN_PROGRESS' ? `${COLORS.yellow}►${COLORS.reset}` : '○';
  const title = truncate(task.title, width - 10);
  const content = `${priority}${status} ${title}`;
  const padding = width - stripAnsi(content).length - 2;

  return BOX.vertical + ' ' + content + ' '.repeat(Math.max(0, padding - 1)) + BOX.vertical;
}

function renderEmptyLine(text: string, width: number): string {
  const content = `${COLORS.dim}${text}${COLORS.reset}`;
  const padding = width - text.length - 2;
  return BOX.vertical + ' ' + content + ' '.repeat(Math.max(0, padding - 1)) + BOX.vertical;
}

function renderHint(hint: string, width: number): string {
  const prefix = `${COLORS.yellow}HINT:${COLORS.reset} `;
  const hintText = truncate(hint, width - 12);
  const content = prefix + hintText;
  const padding = width - stripAnsi(content).length - 2;

  return BOX.vertical + ' ' + content + ' '.repeat(Math.max(0, padding - 1)) + BOX.vertical;
}

function renderStatusBar(ctx: RenderContext, width: number): string {
  const syncStatus = ctx.lastSync
    ? `Synced ${formatTimeAgo(ctx.lastSync)}`
    : 'Not synced';

  const left = ctx.statusMessage || 'Ready';
  const right = syncStatus;
  const padding = width - left.length - right.length - 4;

  return (
    BOX.vertical +
    ' ' +
    `${COLORS.dim}${left}${COLORS.reset}` +
    ' '.repeat(Math.max(1, padding)) +
    `${COLORS.dim}${right}${COLORS.reset}` +
    ' ' +
    BOX.vertical
  );
}

function renderFooter(width: number): string {
  return BOX.bottomLeft + BOX.horizontal.repeat(width - 2) + BOX.bottomRight;
}

// === ACTION BUILDING ===

interface ActionItem {
  type: 'apply_draft' | 'complete_task' | 'create_task' | 'signal';
  label: string;
  entityId?: string;
}

function buildActionList(ctx: RenderContext): ActionItem[] {
  const actions: ActionItem[] = [];

  // Add draft actions
  for (const draft of ctx.drafts.slice(0, 3)) {
    if (draft.state.status === 'PENDING') {
      actions.push({
        type: 'apply_draft',
        label: `Apply: ${truncate(draft.state.summary || 'Draft', 40)}`,
        entityId: draft.entity.entity_id,
      });
    }
  }

  // Add task completion actions
  const inProgress = ctx.tasks.filter(t => t.state.status === 'IN_PROGRESS');
  for (const task of inProgress.slice(0, 2)) {
    actions.push({
      type: 'complete_task',
      label: `Complete: ${truncate(task.state.title, 40)}`,
      entityId: task.entity.entity_id,
    });
  }

  // Mode-specific signals
  if (ctx.cockpit.mode === 'RECOVER') {
    actions.push({
      type: 'signal',
      label: 'Signal: Slept well',
    });
    actions.push({
      type: 'signal',
      label: 'Signal: Feeling better',
    });
  }

  return actions;
}

// === UTILITIES ===

function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen - 3) + '...';
}

function stripAnsi(str: string): string {
  return str.replace(/\x1b\[[0-9;]*m/g, '');
}

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);

  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

// === SIMPLE PROMPTS ===

export function renderPrompt(message: string): string {
  return `${COLORS.cyan}>${COLORS.reset} ${message}: `;
}

export function renderError(message: string): string {
  return `${COLORS.red}Error:${COLORS.reset} ${message}`;
}

export function renderSuccess(message: string): string {
  return `${COLORS.green}✓${COLORS.reset} ${message}`;
}
