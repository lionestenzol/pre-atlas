/**
 * Delta-State Fabric — CLI Application
 *
 * Uses the API server for shared storage with the web app.
 */

import { InputHandler, KeyEvent } from './input';
import { clearScreen, renderPrompt } from './renderer';
import { Mode } from '../core/types';

const API_URL = 'http://localhost:3001/api';

// Types matching API responses
interface SystemState {
  mode: Mode;
  sleepHours: number;
  openLoops: number;
  leverageBalance: number;
  streakDays: number;
}

interface Task {
  id: string;
  title: string;
  status: 'OPEN' | 'IN_PROGRESS' | 'DONE' | 'ARCHIVED';
  priority: 'HIGH' | 'NORMAL' | 'LOW';
  createdAt: number;
}

// ANSI colors
const C = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
  bgRed: '\x1b[41m',
  bgGreen: '\x1b[42m',
  bgYellow: '\x1b[43m',
  bgBlue: '\x1b[44m',
  bgMagenta: '\x1b[45m',
  white: '\x1b[37m',
};

const MODE_COLORS: Record<Mode, string> = {
  RECOVER: C.bgRed,
  CLOSE_LOOPS: C.bgYellow,
  BUILD: C.bgGreen,
  COMPOUND: C.bgBlue,
  SCALE: C.bgMagenta,
};

export class DeltaApp {
  private input: InputHandler;
  private running: boolean = false;
  private apiConnected: boolean = false;

  // State (loaded from API)
  private systemState: SystemState = {
    mode: 'RECOVER',
    sleepHours: 6,
    openLoops: 0,
    leverageBalance: 0,
    streakDays: 0,
  };
  private tasks: Task[] = [];

  // UI state
  private selectedIndex: number = 0;
  private statusMessage: string = '';

  constructor(_dataDir: string) {
    // dataDir param kept for backwards compatibility but not used
    this.input = new InputHandler();
  }

  async start(): Promise<void> {
    this.running = true;
    await this.loadFromAPI();
    this.input.start((event) => this.handleInput(event));
    this.render();

    await new Promise<void>((resolve) => {
      const check = setInterval(() => {
        if (!this.running) {
          clearInterval(check);
          resolve();
        }
      }, 100);
    });
  }

  private async loadFromAPI(): Promise<void> {
    try {
      const [stateRes, tasksRes] = await Promise.all([
        fetch(`${API_URL}/state`),
        fetch(`${API_URL}/tasks`),
      ]);

      if (stateRes.ok && tasksRes.ok) {
        this.systemState = await stateRes.json();
        const allTasks: Task[] = await tasksRes.json();
        this.tasks = allTasks.filter(t => t.status !== 'ARCHIVED');
        this.apiConnected = true;
      } else {
        throw new Error('API returned error');
      }
    } catch (err) {
      this.apiConnected = false;
      this.statusMessage = 'API not connected - start with: npm run api';
    }
  }

  private async saveState(): Promise<void> {
    if (!this.apiConnected) return;

    try {
      await fetch(`${API_URL}/state`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.systemState),
      });
    } catch (err) {
      this.statusMessage = 'Failed to save state';
    }
  }

  private render(): void {
    clearScreen();
    const width = 58;

    // Connection status
    const connStatus = this.apiConnected
      ? `${C.green}● Connected${C.reset}`
      : `${C.red}○ Offline${C.reset}`;

    // Header with mode
    const modeColor = MODE_COLORS[this.systemState.mode];
    console.log(`┌${'─'.repeat(width)}┐`);
    console.log(`│${modeColor}${C.bold}${C.white} MODE: ${this.systemState.mode.padEnd(12)}${C.reset}  ${connStatus}${''.padEnd(width - 35)}│`);
    console.log(`├${'─'.repeat(width)}┤`);

    // Signals
    console.log(`│${C.cyan} SIGNALS${C.reset}${''.padEnd(width - 9)}│`);
    console.log(`│  Sleep: ${this.formatSignal(this.systemState.sleepHours, 7, 5)}h   Loops: ${this.systemState.openLoops} open${''.padEnd(width - 40)}│`);
    console.log(`│  Leverage: ${this.systemState.leverageBalance}   Streak: ${this.systemState.streakDays} days${''.padEnd(width - 38)}│`);
    console.log(`├${'─'.repeat(width)}┤`);

    // Actions
    console.log(`│${C.cyan} ACTIONS${C.reset}${''.padEnd(width - 9)}│`);
    const actions = this.buildActions();

    if (actions.length === 0) {
      console.log(`│${C.dim}  No actions available${C.reset}${''.padEnd(width - 23)}│`);
    } else {
      for (let i = 0; i < actions.length; i++) {
        const sel = i === this.selectedIndex ? `${C.bgBlue}${C.white}` : '';
        const end = i === this.selectedIndex ? C.reset : '';
        const line = `  [${i + 1}] ${actions[i].label}`;
        console.log(`│${sel}${line.padEnd(width)}${end}│`);
      }
    }

    console.log(`├${'─'.repeat(width)}┤`);

    // Tasks
    console.log(`│${C.cyan} TASKS${C.reset}${''.padEnd(width - 7)}│`);
    const openTasks = this.tasks.filter(t => t.status !== 'DONE' && t.status !== 'ARCHIVED').slice(0, 5);

    if (openTasks.length === 0) {
      console.log(`│${C.dim}  No open tasks${C.reset}${''.padEnd(width - 16)}│`);
    } else {
      for (const task of openTasks) {
        const pri = task.priority === 'HIGH' ? `${C.red}!${C.reset}` : ' ';
        const sts = task.status === 'IN_PROGRESS' ? `${C.yellow}►${C.reset}` : '○';
        const title = task.title.length > 45 ? task.title.slice(0, 42) + '...' : task.title;
        console.log(`│  ${pri}${sts} ${title.padEnd(width - 6)}│`);
      }
    }

    console.log(`├${'─'.repeat(width)}┤`);

    // Status
    const status = this.statusMessage || 'Ready';
    console.log(`│${C.dim}  ${status.padEnd(width - 3)}${C.reset}│`);
    console.log(`└${'─'.repeat(width)}┘`);

    // Help
    console.log('');
    console.log(`${C.dim}[↑↓] Navigate  [Enter] Select  [n] New Task  [s] Signal  [r] Refresh  [q] Quit${C.reset}`);
  }

  private formatSignal(value: number, good: number, warn: number): string {
    if (value >= good) return `${C.green}${value}${C.reset}`;
    if (value >= warn) return `${C.yellow}${value}${C.reset}`;
    return `${C.red}${value}${C.reset}`;
  }

  private buildActions(): Array<{ type: string; label: string; id?: string }> {
    const actions: Array<{ type: string; label: string; id?: string }> = [];

    // In-progress task completions
    for (const task of this.tasks.filter(t => t.status === 'IN_PROGRESS').slice(0, 3)) {
      actions.push({
        type: 'complete',
        label: `Complete: ${task.title.slice(0, 40)}`,
        id: task.id,
      });
    }

    // Start task (if in BUILD or higher)
    if (['BUILD', 'COMPOUND', 'SCALE'].includes(this.systemState.mode)) {
      for (const task of this.tasks.filter(t => t.status === 'OPEN').slice(0, 2)) {
        actions.push({
          type: 'start',
          label: `Start: ${task.title.slice(0, 40)}`,
          id: task.id,
        });
      }
    }

    // Mode-specific
    if (this.systemState.mode === 'RECOVER') {
      actions.push({ type: 'signal', label: 'Signal: Slept well (7+ hours)' });
      actions.push({ type: 'signal', label: 'Signal: Feeling better' });
    } else if (this.systemState.mode === 'CLOSE_LOOPS') {
      actions.push({ type: 'signal', label: 'Signal: Cleared my loops' });
    }

    return actions;
  }

  private async handleInput(event: KeyEvent): Promise<void> {
    const actions = this.buildActions();

    switch (event.type) {
      case 'ctrl-c':
        await this.quit();
        break;

      case 'up':
        if (this.selectedIndex > 0) {
          this.selectedIndex--;
          this.render();
        }
        break;

      case 'down':
        if (this.selectedIndex < actions.length - 1) {
          this.selectedIndex++;
          this.render();
        }
        break;

      case 'enter':
        await this.executeAction(actions[this.selectedIndex]);
        break;

      case 'char':
        await this.handleChar(event.char, actions);
        break;
    }
  }

  private async handleChar(
    char: string,
    actions: Array<{ type: string; label: string; id?: string }>
  ): Promise<void> {
    switch (char.toLowerCase()) {
      case 'q':
        await this.quit();
        break;

      case 'n':
        await this.createTask();
        break;

      case 's':
        await this.signalMenu();
        break;

      case 'r':
        await this.refresh();
        break;

      case '1':
      case '2':
      case '3':
      case '4':
      case '5':
      case '6':
      case '7':
        const idx = parseInt(char) - 1;
        if (idx < actions.length) {
          this.selectedIndex = idx;
          await this.executeAction(actions[idx]);
        }
        break;
    }
  }

  private async refresh(): Promise<void> {
    this.statusMessage = 'Refreshing...';
    this.render();
    await this.loadFromAPI();
    this.statusMessage = this.apiConnected ? 'Refreshed from server' : 'API not connected';
    this.render();
  }

  private async executeAction(action: { type: string; label: string; id?: string } | undefined): Promise<void> {
    if (!action) return;

    switch (action.type) {
      case 'complete':
        await this.completeTask(action.id!);
        break;

      case 'start':
        await this.startTask(action.id!);
        break;

      case 'signal':
        await this.handleSignal(action.label);
        break;
    }
  }

  private async createTask(): Promise<void> {
    if (!this.apiConnected) {
      this.statusMessage = 'Cannot create task - API not connected';
      this.render();
      return;
    }

    this.input.stop();
    process.stdout.write('\n' + renderPrompt('Task title'));
    const title = await this.input.prompt('');

    if (title.trim()) {
      try {
        const res = await fetch(`${API_URL}/tasks`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: title.trim() }),
        });

        if (res.ok) {
          const task = await res.json();
          this.tasks.push(task);
          this.systemState.openLoops = this.tasks.filter(t => t.status !== 'DONE' && t.status !== 'ARCHIVED').length;
          this.statusMessage = `Created: ${title.trim()}`;
        } else {
          this.statusMessage = 'Failed to create task';
        }
      } catch (err) {
        this.statusMessage = 'API error creating task';
      }
    }

    this.input.start((event) => this.handleInput(event));
    this.selectedIndex = 0;
    this.render();
  }

  private async startTask(id: string): Promise<void> {
    const task = this.tasks.find(t => t.id === id);
    if (!task) return;

    try {
      const res = await fetch(`${API_URL}/tasks/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'IN_PROGRESS' }),
      });

      if (res.ok) {
        task.status = 'IN_PROGRESS';
        this.statusMessage = `Started: ${task.title}`;
      } else {
        this.statusMessage = 'Failed to start task';
      }
    } catch (err) {
      this.statusMessage = 'API error starting task';
    }

    this.selectedIndex = 0;
    this.render();
  }

  private async completeTask(id: string): Promise<void> {
    const task = this.tasks.find(t => t.id === id);
    if (!task) return;

    try {
      const res = await fetch(`${API_URL}/tasks/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'DONE' }),
      });

      if (res.ok) {
        task.status = 'DONE';
        this.systemState.openLoops = this.tasks.filter(t => t.status !== 'DONE' && t.status !== 'ARCHIVED').length;
        this.systemState.leverageBalance++;
        await this.saveState();
        await this.checkModeTransition();
        this.statusMessage = `Completed: ${task.title}`;
      } else {
        this.statusMessage = 'Failed to complete task';
      }
    } catch (err) {
      this.statusMessage = 'API error completing task';
    }

    this.selectedIndex = 0;
    this.render();
  }

  private async handleSignal(label: string): Promise<void> {
    if (label.includes('Slept well')) {
      this.systemState.sleepHours = 8;
      this.statusMessage = 'Recorded: Good sleep';
    } else if (label.includes('Feeling better')) {
      this.systemState.sleepHours = 7;
      this.statusMessage = 'Recorded: Feeling better';
    } else if (label.includes('Cleared')) {
      this.statusMessage = 'Recorded: Loops cleared';
    }

    await this.saveState();
    await this.checkModeTransition();
    this.render();
  }

  private async signalMenu(): Promise<void> {
    this.input.stop();

    console.log('\n' + C.cyan + 'Signal Update:' + C.reset);
    console.log('  1. Slept well (7+ hours)');
    console.log('  2. Slept poorly (<5 hours)');
    console.log('  3. Completed something big');
    console.log('  4. Feeling overwhelmed');
    console.log('  0. Cancel');

    process.stdout.write(renderPrompt('Choice'));
    const choice = await this.input.prompt('');

    switch (choice) {
      case '1':
        this.systemState.sleepHours = 8;
        this.statusMessage = 'Recorded: Good sleep';
        break;
      case '2':
        this.systemState.sleepHours = 4;
        this.statusMessage = 'Recorded: Poor sleep';
        break;
      case '3':
        this.systemState.leverageBalance += 2;
        this.systemState.streakDays++;
        this.statusMessage = 'Recorded: Big win! Leverage +2';
        break;
      case '4':
        this.systemState.mode = 'RECOVER';
        this.statusMessage = 'Entering RECOVER mode';
        break;
    }

    await this.saveState();
    await this.checkModeTransition();

    this.input.start((event) => this.handleInput(event));
    this.render();
  }

  private async checkModeTransition(): Promise<void> {
    const { mode, sleepHours, openLoops, leverageBalance, streakDays } = this.systemState;
    let newMode = mode;

    // Critical sleep forces RECOVER
    if (sleepHours < 5) {
      newMode = 'RECOVER';
    }
    // Low sleep restricts to RECOVER or CLOSE_LOOPS
    else if (sleepHours < 7) {
      if (mode === 'BUILD' || mode === 'COMPOUND' || mode === 'SCALE') {
        newMode = 'CLOSE_LOOPS';
      }
    }
    // Sleep OK — can progress
    else {
      if (mode === 'RECOVER') {
        newMode = 'CLOSE_LOOPS';
      } else if (mode === 'CLOSE_LOOPS' && openLoops <= 3) {
        newMode = 'BUILD';
      } else if (mode === 'BUILD' && leverageBalance >= 5) {
        newMode = 'COMPOUND';
      } else if (mode === 'COMPOUND' && leverageBalance >= 10 && streakDays >= 3) {
        newMode = 'SCALE';
      }
    }

    // Many loops forces back
    if (openLoops > 7 && (mode === 'BUILD' || mode === 'COMPOUND' || mode === 'SCALE')) {
      newMode = 'CLOSE_LOOPS';
    }

    if (newMode !== mode) {
      this.statusMessage = `Mode: ${mode} → ${newMode}`;
      this.systemState.mode = newMode;
      await this.saveState();
    }
  }

  private async quit(): Promise<void> {
    this.input.stop();

    clearScreen();
    console.log('Delta-State Fabric shut down.\n');

    console.log(`Mode: ${this.systemState.mode}`);
    console.log(`Tasks: ${this.tasks.filter(t => t.status !== 'DONE' && t.status !== 'ARCHIVED').length} open`);
    console.log(`Connection: ${this.apiConnected ? 'API synced' : 'Offline'}`);

    this.running = false;
    process.exit(0);
  }
}
