/**
 * Delta-State Fabric — Input Handler
 *
 * Handles keyboard input for the CLI.
 * Uses raw mode for single keypress detection.
 */

import * as readline from 'readline';

export type KeyEvent =
  | { type: 'up' }
  | { type: 'down' }
  | { type: 'enter' }
  | { type: 'char'; char: string }
  | { type: 'escape' }
  | { type: 'backspace' }
  | { type: 'ctrl-c' };

export type KeyHandler = (event: KeyEvent) => void;

export class InputHandler {
  private handler: KeyHandler | null = null;
  private rl: readline.Interface | null = null;

  start(handler: KeyHandler): void {
    this.handler = handler;

    // Enable raw mode for single keypress detection
    if (process.stdin.isTTY) {
      process.stdin.setRawMode(true);
    }
    process.stdin.resume();
    process.stdin.setEncoding('utf8');

    process.stdin.on('data', (key: string) => {
      this.handleKey(key);
    });
  }

  stop(): void {
    if (process.stdin.isTTY) {
      process.stdin.setRawMode(false);
    }
    process.stdin.pause();
    this.handler = null;
  }

  private handleKey(key: string): void {
    if (!this.handler) return;

    // Ctrl+C
    if (key === '\x03') {
      this.handler({ type: 'ctrl-c' });
      return;
    }

    // Escape
    if (key === '\x1b' || key === '\x1b\x1b') {
      this.handler({ type: 'escape' });
      return;
    }

    // Arrow keys (escape sequences)
    if (key === '\x1b[A') {
      this.handler({ type: 'up' });
      return;
    }
    if (key === '\x1b[B') {
      this.handler({ type: 'down' });
      return;
    }

    // Enter
    if (key === '\r' || key === '\n') {
      this.handler({ type: 'enter' });
      return;
    }

    // Backspace
    if (key === '\x7f' || key === '\b') {
      this.handler({ type: 'backspace' });
      return;
    }

    // Regular character
    if (key.length === 1 && key >= ' ' && key <= '~') {
      this.handler({ type: 'char', char: key });
      return;
    }
  }

  // Prompt for text input (exits raw mode temporarily)
  async prompt(message: string): Promise<string> {
    return new Promise((resolve) => {
      // Temporarily exit raw mode
      if (process.stdin.isTTY) {
        process.stdin.setRawMode(false);
      }

      this.rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout,
      });

      this.rl.question(message, (answer) => {
        this.rl?.close();
        this.rl = null;

        // Re-enable raw mode
        if (process.stdin.isTTY) {
          process.stdin.setRawMode(true);
        }

        resolve(answer);
      });
    });
  }

  // Prompt for confirmation
  async confirm(message: string): Promise<boolean> {
    const answer = await this.prompt(`${message} (y/n): `);
    return answer.toLowerCase() === 'y' || answer.toLowerCase() === 'yes';
  }
}
