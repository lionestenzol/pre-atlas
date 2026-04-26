import type { AnatomyV1 } from '../adapter/v1-schema.js';

export interface EditEvent {
  timestamp: number;
  intent: string;
  targetId: string;
  outcome: 'applied' | 'unresolved' | 'error' | 'noop';
  filesChanged: string[];
  message?: string;
}

export interface CloneSessionState {
  sessionId: string;
  envelope: AnatomyV1;
  capturePath: string;
  url: string;
  rootDir: string;
  edits: EditEvent[];
  createdAt: number;
}

export interface RegisterCloneArgs {
  sessionId: string;
  envelope: AnatomyV1;
  capturePath: string;
  url: string;
  rootDir: string;
}

export class SessionStore {
  private readonly sessions = new Map<string, CloneSessionState>();

  public registerClone(args: RegisterCloneArgs): CloneSessionState {
    const state: CloneSessionState = {
      sessionId: args.sessionId,
      envelope: args.envelope,
      capturePath: args.capturePath,
      url: args.url,
      rootDir: args.rootDir,
      edits: [],
      createdAt: Date.now(),
    };
    this.sessions.set(args.sessionId, state);
    return state;
  }

  public getState(sessionId: string): CloneSessionState | undefined {
    return this.sessions.get(sessionId);
  }

  public recordEdit(sessionId: string, event: EditEvent): void {
    const state = this.sessions.get(sessionId);
    if (state === undefined) {
      return;
    }
    state.edits.push(event);
  }

  public remove(sessionId: string): void {
    this.sessions.delete(sessionId);
  }

  public list(): ReadonlyArray<CloneSessionState> {
    return [...this.sessions.values()];
  }
}
