// canvas-engine Phase 4 · edit loop · region/chain edits via deterministic string transforms

import { readFile } from 'node:fs/promises';
import path from 'node:path';
import type { AnatomyV1, Region } from '../adapter/v1-schema.js';
import {
  buildEditPrompt,
  resolveEditTarget,
  type EditTarget,
} from '../adapter/v1-to-edit-prompt.js';
import type { VitePool } from '../sandbox/vite-pool.js';
import type { CloneSessionState, EditEvent } from './session-store.js';
import type { SessionStore } from './session-store.js';

export type EditEventStream =
  | {
      type: 'status';
      phase: 'resolve' | 'edit-prompt' | 'parse-intent' | 'apply' | 'done';
      message: string;
    }
  | { type: 'preamble'; preview: string }
  | { type: 'file'; path: string; content: string }
  | {
      type: 'done';
      sessionId: string;
      url: string;
      intent: string;
      targetId: string;
      outcome: EditEvent['outcome'];
      filesChanged: string[];
    }
  | { type: 'error'; phase: string; message: string };

export interface EditOptions {
  sessionId: string;
  intent: string;
  targetId: string;
}

export interface EditDeps {
  pool: VitePool;
  store: SessionStore;
}

interface DeterministicEdit {
  kind: 'tint' | 'rename' | 'hide' | 'note';
  color?: string;
  newName?: string;
  text?: string;
}

const TAILWIND_COLORS = [
  'red', 'orange', 'amber', 'yellow', 'lime', 'green', 'emerald',
  'teal', 'cyan', 'sky', 'blue', 'indigo', 'violet', 'purple',
  'fuchsia', 'pink', 'rose', 'slate', 'gray', 'zinc', 'neutral', 'stone',
] as const;

const LAYER_TINTS: Record<Region['layer'], string> = {
  ui: 'bg-purple-50',
  api: 'bg-amber-50',
  ext: 'bg-sky-50',
  lib: 'bg-emerald-50',
  state: 'bg-rose-50',
};

function formatErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function toPascalCase(value: string): string {
  const cleaned = value
    .split(/[\s-]+/)
    .map((part) => part.replace(/[^a-zA-Z0-9]/g, ''))
    .filter((part) => part.length > 0)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1));
  const joined = cleaned.join('');
  return /^[0-9]/.test(joined) ? `R${joined}` : joined;
}

function buildSeenNameMap(envelope: AnatomyV1): Map<string, string> {
  const seen = new Map<string, number>();
  const result = new Map<string, string>();
  const sorted = [...envelope.regions].sort((l, r) => l.n - r.n);
  for (const region of sorted) {
    const baseName = toPascalCase(region.name) || `Region${region.n}`;
    const idx = seen.get(baseName) ?? 0;
    seen.set(baseName, idx + 1);
    const componentName = idx === 0 ? baseName : `${baseName}${region.n}`;
    result.set(region.id, componentName);
  }
  return result;
}

function parseDeterministicIntent(intent: string): DeterministicEdit {
  const lower = intent.toLowerCase();

  const colorMatch = lower.match(
    new RegExp(`\\b(${TAILWIND_COLORS.join('|')})\\b`),
  );
  if (colorMatch) {
    return { kind: 'tint', color: colorMatch[1] };
  }

  const renameMatch = intent.match(/(?:rename|name|call)\b[^]*?\bto\s+["']?([A-Za-z][A-Za-z0-9 ]{0,40})["']?\s*\.?$/i);
  if (renameMatch) {
    return { kind: 'rename', newName: renameMatch[1].trim() };
  }

  if (/\b(hide|remove|delete|drop)\b/.test(lower)) {
    return { kind: 'hide' };
  }

  return { kind: 'note', text: intent };
}

async function readSessionFile(rootDir: string, relPath: string): Promise<string> {
  const absPath = path.join(rootDir, relPath);
  return await readFile(absPath, 'utf8');
}

function applyTintEdit(content: string, region: Region, color: string): string {
  const oldClass = LAYER_TINTS[region.layer];
  const newClass = `bg-${color}-100`;
  return content.replace(oldClass, newClass);
}

function applyRenameEdit(content: string, newName: string): string {
  const escaped = newName.replace(/[\\"]/g, (m) => `\\${m}`);
  return content.replace(
    /(<h2[^>]*?>)\s*\{?["']?[^"'<{}]*["']?\}?\s*(<\/h2>)/,
    `$1${escaped}$2`,
  );
}

function applyHideEdit(appContent: string, componentName: string): string {
  const importRe = new RegExp(
    `^\\s*import\\s+${componentName}\\s+from[^;]+;?\\s*$\\n?`,
    'm',
  );
  const usageRe = new RegExp(`\\s*<${componentName}\\s*\\/>\\s*\\n?`, 'g');
  return appContent.replace(importRe, '').replace(usageRe, '\n');
}

function applyNoteEdit(content: string, note: string): string {
  const safeNote = note.replace(/\*\//g, '*\\/');
  const block = `// edit-note: ${safeNote}\n`;
  return block + content;
}

interface FileChange {
  path: string;
  content: string;
}

async function buildFileChanges(
  state: CloneSessionState,
  target: EditTarget,
  edit: DeterministicEdit,
): Promise<{ files: FileChange[]; outcome: EditEvent['outcome']; message?: string }> {
  if (target.kind === 'unresolved') {
    return { files: [], outcome: 'unresolved', message: `id "${target.id}" not in regions[] or chains[]` };
  }

  const componentNames = buildSeenNameMap(state.envelope);

  if (target.kind === 'region') {
    const region = target.region;
    const componentName = componentNames.get(region.id);
    if (!componentName) {
      return { files: [], outcome: 'error', message: `cannot resolve component name for region ${region.id}` };
    }
    const componentRel = `src/components/${componentName}.jsx`;
    const appRel = 'src/App.jsx';

    if (edit.kind === 'tint' && edit.color) {
      const before = await readSessionFile(state.rootDir, componentRel);
      const after = applyTintEdit(before, region, edit.color);
      if (before === after) {
        return { files: [], outcome: 'noop', message: `tint already ${edit.color} or layer tint not present` };
      }
      return { files: [{ path: componentRel, content: after }], outcome: 'applied' };
    }

    if (edit.kind === 'rename' && edit.newName) {
      const before = await readSessionFile(state.rootDir, componentRel);
      const after = applyRenameEdit(before, edit.newName);
      if (before === after) {
        return { files: [], outcome: 'noop', message: 'rename target h2 not found' };
      }
      return { files: [{ path: componentRel, content: after }], outcome: 'applied' };
    }

    if (edit.kind === 'hide') {
      const beforeApp = await readSessionFile(state.rootDir, appRel);
      const afterApp = applyHideEdit(beforeApp, componentName);
      if (beforeApp === afterApp) {
        return { files: [], outcome: 'noop', message: `${componentName} not present in App.jsx` };
      }
      return { files: [{ path: appRel, content: afterApp }], outcome: 'applied' };
    }

    if (edit.kind === 'note' && edit.text) {
      const before = await readSessionFile(state.rootDir, componentRel);
      const after = applyNoteEdit(before, edit.text);
      return { files: [{ path: componentRel, content: after }], outcome: 'applied' };
    }
  }

  if (target.kind === 'chain') {
    return {
      files: [],
      outcome: 'noop',
      message: 'chain edits emit a note only in Phase 4 stub · real LLM applies cross-file edits in Phase 4b',
    };
  }

  return { files: [], outcome: 'error', message: 'unhandled edit kind' };
}

export async function* runEdit(
  opts: EditOptions,
  deps: EditDeps,
): AsyncGenerator<EditEventStream> {
  yield {
    type: 'status',
    phase: 'resolve',
    message: `resolving session ${opts.sessionId} · target id ${opts.targetId}`,
  };

  const state = deps.store.getState(opts.sessionId);
  if (state === undefined) {
    yield { type: 'error', phase: 'resolve', message: `session ${opts.sessionId} not found in store` };
    return;
  }

  if (deps.pool.getSession(opts.sessionId) === undefined) {
    yield { type: 'error', phase: 'resolve', message: `session ${opts.sessionId} not active in pool` };
    return;
  }

  yield { type: 'status', phase: 'edit-prompt', message: 'building focused edit prompt' };

  let prompt: string;
  try {
    prompt = buildEditPrompt(state.envelope, { id: opts.targetId, intent: opts.intent });
  } catch (err) {
    yield { type: 'error', phase: 'edit-prompt', message: formatErrorMessage(err) };
    return;
  }
  yield { type: 'preamble', preview: prompt.slice(0, 200) };

  yield { type: 'status', phase: 'parse-intent', message: 'parsing intent (deterministic stub)' };
  const edit = parseDeterministicIntent(opts.intent);
  const target = resolveEditTarget(state.envelope, opts.targetId);

  yield { type: 'status', phase: 'apply', message: `applying ${edit.kind} edit` };

  let result: { files: FileChange[]; outcome: EditEvent['outcome']; message?: string };
  try {
    result = await buildFileChanges(state, target, edit);
  } catch (err) {
    const message = formatErrorMessage(err);
    yield { type: 'error', phase: 'apply', message };
    deps.store.recordEdit(opts.sessionId, {
      timestamp: Date.now(),
      intent: opts.intent,
      targetId: opts.targetId,
      outcome: 'error',
      filesChanged: [],
      message,
    });
    return;
  }

  if (result.files.length > 0) {
    try {
      await deps.pool.writeFiles(opts.sessionId, result.files);
    } catch (err) {
      const message = formatErrorMessage(err);
      yield { type: 'error', phase: 'apply', message };
      deps.store.recordEdit(opts.sessionId, {
        timestamp: Date.now(),
        intent: opts.intent,
        targetId: opts.targetId,
        outcome: 'error',
        filesChanged: [],
        message,
      });
      return;
    }
  }

  for (const file of result.files) {
    yield { type: 'file', path: file.path, content: file.content };
  }

  const filesChanged = result.files.map((f) => f.path);
  deps.store.recordEdit(opts.sessionId, {
    timestamp: Date.now(),
    intent: opts.intent,
    targetId: opts.targetId,
    outcome: result.outcome,
    filesChanged,
    message: result.message,
  });

  yield {
    type: 'status',
    phase: 'done',
    message: `outcome ${result.outcome} · ${filesChanged.length} file(s) changed`,
  };
  yield {
    type: 'done',
    sessionId: opts.sessionId,
    url: state.url,
    intent: opts.intent,
    targetId: opts.targetId,
    outcome: result.outcome,
    filesChanged,
  };
}

export const __test = {
  parseDeterministicIntent,
  applyTintEdit,
  applyRenameEdit,
  applyHideEdit,
  applyNoteEdit,
  toPascalCase,
  buildSeenNameMap,
};
