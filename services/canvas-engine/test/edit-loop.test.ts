// canvas-engine Phase 4 · edit-loop test suite · vitest

import { beforeEach, describe, expect, it } from 'vitest';
import { mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

import realistic from './fixtures/anatomy-v1-realistic.json';

import {
  runEdit,
  type EditDeps,
  type EditEventStream,
  type EditOptions,
  __test,
} from '../src/pipeline/edit-loop.js';
import {
  SessionStore,
  type CloneSessionState,
} from '../src/pipeline/session-store.js';
import {
  anatomyV1Schema,
  type AnatomyV1,
  type Region,
} from '../src/adapter/v1-schema.js';
import type { SessionInfo } from '../src/sandbox/vite-pool.js';

const realisticEnvelope: AnatomyV1 = anatomyV1Schema.parse(realistic);

interface MockWrittenFile {
  path: string;
  content: string;
}

interface MockPoolConfig {
  sessionId: string;
  rootDir: string;
  capturedFiles: MockWrittenFile[];
}

interface MockPoolLike {
  allocate(): Promise<SessionInfo>;
  release(sessionId: string): Promise<void>;
  shutdown(): Promise<void>;
  listActive(): SessionInfo[];
  getSession(sessionId: string): SessionInfo | undefined;
  writeFiles(
    sessionId: string,
    files: Array<{ path: string; content: string }>,
  ): Promise<void>;
}

function createMockPool(config: MockPoolConfig): MockPoolLike {
  const sessionInfo: SessionInfo = {
    sessionId: config.sessionId,
    port: 3060,
    rootDir: config.rootDir,
    url: 'http://localhost:3060',
    createdAt: 0,
    lastActivity: 0,
  };

  return {
    async allocate(): Promise<SessionInfo> {
      return sessionInfo;
    },
    async release(_sessionId: string): Promise<void> {},
    async shutdown(): Promise<void> {},
    listActive(): SessionInfo[] {
      return [sessionInfo];
    },
    getSession(sessionId: string): SessionInfo | undefined {
      return sessionId === config.sessionId ? sessionInfo : undefined;
    },
    async writeFiles(
      sessionId: string,
      files: Array<{ path: string; content: string }>,
    ): Promise<void> {
      if (sessionId !== config.sessionId) {
        throw new Error(`Unknown session: ${sessionId}`);
      }

      config.capturedFiles.push(...files);
    },
  };
}

function buildDeps(
  store: SessionStore,
  pool: MockPoolLike,
): EditDeps {
  return {
    store,
    pool: pool as unknown as EditDeps['pool'],
  };
}

function registerRealisticSession(
  store: SessionStore,
  sessionId: string,
  rootDir: string,
): CloneSessionState {
  return store.registerClone({
    sessionId,
    envelope: realisticEnvelope,
    capturePath: path.join(rootDir, 'capture.json'),
    url: 'http://localhost:3060',
    rootDir,
  });
}

async function collectEvents(
  opts: EditOptions,
  deps: EditDeps,
): Promise<EditEventStream[]> {
  const events: EditEventStream[] = [];
  for await (const event of runEdit(opts, deps)) {
    events.push(event);
  }
  return events;
}

function expectDoneEvent(events: EditEventStream[]): Extract<EditEventStream, { type: 'done' }> {
  const doneEvent = events.find((event) => event.type === 'done');
  expect(doneEvent).toBeDefined();
  if (doneEvent === undefined || doneEvent.type !== 'done') {
    throw new Error('Expected done event');
  }
  return doneEvent;
}

function expectErrorEvent(events: EditEventStream[]): Extract<EditEventStream, { type: 'error' }> {
  const errorEvent = events.find((event) => event.type === 'error');
  expect(errorEvent).toBeDefined();
  if (errorEvent === undefined || errorEvent.type !== 'error') {
    throw new Error('Expected error event');
  }
  return errorEvent;
}

function findRegion(id: string): Region {
  const region = realisticEnvelope.regions.find((entry) => entry.id === id);
  if (region === undefined) {
    throw new Error(`Missing fixture region ${id}`);
  }
  return region;
}

describe('__test.parseDeterministicIntent · pattern coverage', () => {
  it('covers tint, rename, hide, and note fallbacks', () => {
    expect(__test.parseDeterministicIntent('make region 7 red')).toEqual({
      kind: 'tint',
      color: 'red',
    });
    expect(__test.parseDeterministicIntent('change the bg to blue')).toEqual({
      kind: 'tint',
      color: 'blue',
    });
    expect(
      __test.parseDeterministicIntent('rename the search bar to Quick Search'),
    ).toEqual({
      kind: 'rename',
      newName: 'Quick Search',
    });
    expect(__test.parseDeterministicIntent('hide the footer')).toEqual({
      kind: 'hide',
    });
    expect(__test.parseDeterministicIntent('remove the hero section')).toEqual({
      kind: 'hide',
    });
    expect(
      __test.parseDeterministicIntent('please add aria-label'),
    ).toEqual({
      kind: 'note',
      text: 'please add aria-label',
    });
  });
});

describe('__test.applyTintEdit · region tint replacement', () => {
  it('replaces a ui layer tint and preserves the surrounding content', () => {
    const region = findRegion('header-nav');
    const before = [
      'export function Header() {',
      '  return <section className="rounded-lg bg-purple-50 px-4 py-3 text-slate-900">Header</section>;',
      '}',
    ].join('\n');

    const after = __test.applyTintEdit(before, region, 'red');

    expect(after).toContain('bg-red-100');
    expect(after).not.toContain('bg-purple-50');
    expect(after.replace('bg-red-100', 'bg-purple-50')).toBe(before);
  });

  it('replaces a state layer tint with the new color scale', () => {
    const region: Region = {
      id: 'client-state',
      n: 99,
      name: 'Client state',
      layer: 'state',
    };
    const before =
      'export const StatePanel = () => <aside className="bg-rose-50 text-sm">State</aside>;';

    const after = __test.applyTintEdit(before, region, 'emerald');

    expect(after).toContain('bg-emerald-100');
    expect(after).not.toContain('bg-rose-50');
  });

  it('returns the original content when the layer tint is absent', () => {
    const region = findRegion('hero');
    const before =
      'export function Hero() { return <section className="bg-white text-slate-900">Hero</section>; }';

    const after = __test.applyTintEdit(before, region, 'red');

    expect(after).toBe(before);
  });
});

describe('__test.applyRenameEdit · h2 text replacement', () => {
  it('replaces h2 text for plain text and jsx-expression headings', () => {
    const plain =
      '<section><h2 className="text-lg font-semibold">Search bar</h2></section>';
    const jsxExpression =
      '<section><h2 className="text-lg font-semibold">{"Search bar"}</h2></section>';

    expect(__test.applyRenameEdit(plain, 'Quick Search')).toContain(
      '>Quick Search</h2>',
    );
    expect(__test.applyRenameEdit(jsxExpression, 'Quick Search')).toContain(
      '>Quick Search</h2>',
    );
  });

  it('returns the original content when no h2 is present', () => {
    const before =
      '<section><p className="text-sm text-slate-600">Search bar</p></section>';

    expect(__test.applyRenameEdit(before, 'Quick Search')).toBe(before);
  });
});

describe('__test.applyHideEdit · App.jsx import + usage removal', () => {
  it('removes the target import and usage while preserving other components', () => {
    const before = [
      "import Header from './components/Header.jsx';",
      "import Hero from './components/Hero.jsx';",
      "import Footer from './components/Footer.jsx';",
      '',
      'export default function App() {',
      '  return (',
      '    <main>',
      '      <Header />',
      '      <Hero />',
      '      <Footer />',
      '    </main>',
      '  );',
      '}',
    ].join('\n');

    const after = __test.applyHideEdit(before, 'Footer');

    expect(after).not.toContain("import Footer from './components/Footer.jsx';");
    expect(after).not.toContain('<Footer />');
    expect(after).toContain("import Header from './components/Header.jsx';");
    expect(after).toContain("import Hero from './components/Hero.jsx';");
    expect(after).toContain('<Header />');
    expect(after).toContain('<Hero />');
  });
});

describe('__test.buildSeenNameMap · component name collisions handled', () => {
  it('builds valid PascalCase names for all realistic fixture region ids', () => {
    const seenNameMap = __test.buildSeenNameMap(realisticEnvelope);
    const expectedIds = [
      'header-nav',
      'search-bar',
      'hero',
      'product-grid',
      'footer',
    ];

    expect([...seenNameMap.keys()].sort()).toEqual([...expectedIds].sort());

    for (const regionId of expectedIds) {
      const componentName = seenNameMap.get(regionId);
      expect(componentName).toBeDefined();
      expect(componentName).toMatch(/^[A-Z][A-Za-z0-9]*$/);
    }
  });
});

describe('runEdit · end-to-end on a stubbed session (3 ground-truth prompts)', () => {
  let tempRoot = '';
  let store: SessionStore;
  let capturedFiles: MockWrittenFile[];
  let deps: EditDeps;
  const sessionId = 'cs-phase4';

  beforeEach(async () => {
    if (tempRoot) {
      await rm(tempRoot, { recursive: true, force: true });
    }

    tempRoot = path.join(
      tmpdir(),
      `canvas-engine-edit-loop-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    );
    await mkdir(path.join(tempRoot, 'src', 'components'), { recursive: true });

    store = new SessionStore();
    capturedFiles = [];
    const pool = createMockPool({
      sessionId,
      rootDir: tempRoot,
      capturedFiles,
    });
    deps = buildDeps(store, pool);
    registerRealisticSession(store, sessionId, tempRoot);
  });

  it('applies a tint edit to the target component file', async () => {
    const headerPath = path.join(tempRoot, 'src', 'components', 'Header.jsx');
    await writeFile(
      headerPath,
      [
        'export default function Header() {',
        '  return <header className="bg-purple-50 px-4 py-3 text-slate-900">Header</header>;',
        '}',
      ].join('\n'),
      'utf8',
    );

    const events = await collectEvents(
      {
        sessionId,
        targetId: 'header-nav',
        intent: 'make Header red',
      },
      deps,
    );

    const doneEvent = expectDoneEvent(events);
    expect(doneEvent.outcome).toBe('applied');
    expect(doneEvent.filesChanged).toHaveLength(1);
    expect(doneEvent.filesChanged[0]).toMatch(/Header\.jsx$/);
    expect(capturedFiles).toHaveLength(1);
    expect(capturedFiles[0]?.path).toBe('src/components/Header.jsx');
    expect(capturedFiles[0]?.content).toContain('bg-red-100');
  });

  it('applies a rename edit to the target component heading', async () => {
    const searchBarPath = path.join(
      tempRoot,
      'src',
      'components',
      'SearchBar.jsx',
    );
    await writeFile(
      searchBarPath,
      [
        'export default function SearchBar() {',
        '  return <section><h2>Search bar</h2></section>;',
        '}',
      ].join('\n'),
      'utf8',
    );

    const events = await collectEvents(
      {
        sessionId,
        targetId: 'search-bar',
        intent: 'rename search-bar to Quick Search',
      },
      deps,
    );

    const doneEvent = expectDoneEvent(events);
    expect(doneEvent.outcome).toBe('applied');
    expect(doneEvent.filesChanged).toHaveLength(1);
    expect(doneEvent.filesChanged[0]).toBe('src/components/SearchBar.jsx');
    expect(capturedFiles).toHaveLength(1);
    expect(capturedFiles[0]?.content).toContain('Quick Search');
  });

  it('applies a hide edit by removing the component from App.jsx', async () => {
    const appPath = path.join(tempRoot, 'src', 'App.jsx');
    await writeFile(
      appPath,
      [
        "import Header from './components/Header.jsx';",
        "import Hero from './components/Hero.jsx';",
        "import Footer from './components/Footer.jsx';",
        '',
        'export default function App() {',
        '  return (',
        '    <main>',
        '      <Header />',
        '      <Hero />',
        '      <Footer />',
        '    </main>',
        '  );',
        '}',
      ].join('\n'),
      'utf8',
    );

    const events = await collectEvents(
      {
        sessionId,
        targetId: 'footer',
        intent: 'hide footer',
      },
      deps,
    );

    const doneEvent = expectDoneEvent(events);
    expect(doneEvent.outcome).toBe('applied');
    expect(doneEvent.filesChanged).toEqual(['src/App.jsx']);
    expect(capturedFiles).toHaveLength(1);
    expect(capturedFiles[0]?.content).not.toContain('<Footer />');
    expect(capturedFiles[0]?.content).toContain('<Header />');
    expect(capturedFiles[0]?.content).toContain('<Hero />');
  });
});

describe('runEdit · unresolved target', () => {
  let tempRoot = '';
  let store: SessionStore;
  let deps: EditDeps;
  const sessionId = 'cs-unresolved';

  beforeEach(async () => {
    if (tempRoot) {
      await rm(tempRoot, { recursive: true, force: true });
    }

    tempRoot = path.join(
      tmpdir(),
      `canvas-engine-edit-loop-unresolved-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    );
    await mkdir(path.join(tempRoot, 'src', 'components'), { recursive: true });

    store = new SessionStore();
    const pool = createMockPool({
      sessionId,
      rootDir: tempRoot,
      capturedFiles: [],
    });
    deps = buildDeps(store, pool);
    registerRealisticSession(store, sessionId, tempRoot);
  });

  it('emits a done event with unresolved outcome and no changed files', async () => {
    const events = await collectEvents(
      {
        sessionId,
        targetId: 'does-not-exist',
        intent: 'make it blue',
      },
      deps,
    );

    const doneEvent = expectDoneEvent(events);
    expect(doneEvent.outcome).toBe('unresolved');
    expect(doneEvent.filesChanged).toEqual([]);
  });
});

describe('runEdit · session-not-found', () => {
  it('emits a single resolve-phase error event for an unknown session', async () => {
    const store = new SessionStore();
    const pool = createMockPool({
      sessionId: 'cs-nope',
      rootDir: path.join(tmpdir(), 'canvas-engine-edit-loop-missing'),
      capturedFiles: [],
    });
    const events = await collectEvents(
      {
        sessionId: 'cs-nope',
        targetId: 'header-nav',
        intent: 'make Header red',
      },
      buildDeps(store, pool),
    );

    const errorEvent = expectErrorEvent(events);
    expect(errorEvent.phase).toBe('resolve');
    expect(events.filter((e) => e.type === 'error')).toHaveLength(1);
  });
});
