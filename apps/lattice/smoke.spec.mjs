import { test, expect } from '@playwright/test';

// Hermetic smoke for the Week-3 graph refactor (commit 0df6d01). It mocks the
// two delta-kernel :3001 endpoints the page calls, so no live backend is needed,
// and guards the exact invariants the refactor established:
//   1. The server projection is the single source of truth for the graph.
//   2. A settings toggle re-renders only — it does NOT re-derive nodes/edges
//      (the old dual-write race), so window.nodes is unchanged across a toggle.
//   3. nodeVisible() is the single masking gate (showProjects off -> 0 project nodes).
//   4. Ghost stubs come from one shared makeGhostStub: server path omits project,
//      derive (fallback) path carries the owning item's project.
//   5. Fallback fires only when the server sent items but no nodes/edges.

const TOKEN = { token: 'smoke-token' };

// Two items: i1(atlas) -blocks-> i2(lattice); i2 -relates-> canon_ghost1 (a
// dangling endpoint with no item, so it must be ghost-stubbed).
const ITEMS = [
  { id: 'i1', title: 'Item One', project: 'atlas', status: 'open',
    time: '2026-06-25', links: [{ kind: 'blocks', to: 'i2' }], provenance: { source: 'test' } },
  { id: 'i2', title: 'Item Two', project: 'lattice', status: 'active',
    time: '2026-06-25', links: [{ kind: 'relates', to: 'canon_ghost1' }], provenance: { source: 'test' } },
];
const PROJECTS = [{ id: 'atlas', name: 'atlas' }, { id: 'lattice', name: 'lattice' }];

// Server-projection graph (the live path): project + item nodes, belongs_to +
// link edges, and one edge endpoint (canon_ghost1) absent from nodes -> ghost.
const SERVER_NODES = [
  { id: 'i1', type: 'item', label: 'Item One', project: 'atlas', status: 'open' },
  { id: 'i2', type: 'item', label: 'Item Two', project: 'lattice', status: 'active' },
  { id: 'project:atlas', type: 'project', label: 'atlas', project: 'atlas' },
  { id: 'project:lattice', type: 'project', label: 'lattice', project: 'lattice' },
];
const SERVER_EDGES = [
  { from: 'i1', to: 'project:atlas', kind: 'belongs_to' },
  { from: 'i2', to: 'project:lattice', kind: 'belongs_to' },
  { from: 'i1', to: 'i2', kind: 'blocks' },
  { from: 'i2', to: 'canon_ghost1', kind: 'relates' },
];

function viewmodel(nodes, edges) {
  return { ok: true, viewmodel: { items: ITEMS, events: [], projects: PROJECTS, nodes, edges } };
}

async function mockBackend(page, nodes, edges) {
  await page.route('**/api/auth/token', (r) => r.fulfill({ json: TOKEN }));
  await page.route('**/api/lattice/viewmodel', (r) => r.fulfill({ json: viewmodel(nodes, edges) }));
  // Backbone /items feed (atlas-map-api) — return empty so loadBackbone is inert.
  await page.route('**/items', (r) => r.fulfill({ json: { items: [] } }));
  await page.route('**/items?**', (r) => r.fulfill({ json: { items: [] } }));
}

async function bootGraph(page) {
  await page.waitForFunction(() => window.latticeSync && Array.isArray(window.nodes) && window.nodes.length > 0);
  await page.evaluate(() => switchView('graph'));
  await page.waitForFunction(() => typeof cy === 'object' && cy && cy.nodes().length > 0);
}

const setKnob = (sel, checked) =>
  `(() => { const el = document.querySelector('${sel}'); el.checked = ${checked}; el.dispatchEvent(new Event('change', { bubbles: true })); })()`;

test('server projection is the source of truth: ghost-stub, masking, and no re-derive race', async ({ page }) => {
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));

  await mockBackend(page, SERVER_NODES, SERVER_EDGES);
  await page.goto('/index.html');
  await bootGraph(page);

  // Ghost stub synthesized from the dangling edge endpoint; server path omits project.
  const ghost = await page.evaluate(() => window.nodes.find((n) => n.id === 'canon_ghost1'));
  expect(ghost, 'ghost stub for dangling endpoint').toBeTruthy();
  expect(ghost.provenance.ghost).toBe(true);
  expect('project' in ghost, 'server-path ghost omits project').toBe(false);

  // Widen to the full neighborhood so project nodes are in view.
  await page.evaluate(setKnob('input[name="depth"][value="all"]', true));
  await page.waitForTimeout(400);

  const nodesBefore = await page.evaluate(() => window.nodes.length);
  const projBefore = await page.evaluate(() => cy.nodes().filter((n) => n.data('type') === 'project').length);
  expect(projBefore, 'project nodes visible before masking').toBeGreaterThan(0);

  // Toggle showProjects OFF: must re-render via nodeVisible WITHOUT re-deriving.
  await page.evaluate(setKnob('input[data-knob="showProjects"]', false));
  await page.waitForTimeout(400);

  const nodesAfter = await page.evaluate(() => window.nodes.length);
  const projAfter = await page.evaluate(() => cy.nodes().filter((n) => n.data('type') === 'project').length);

  expect(nodesAfter, 'no re-derive race: window.nodes unchanged by a settings toggle').toBe(nodesBefore);
  expect(projAfter, 'nodeVisible masks project nodes at render').toBe(0);
  expect(errors, 'no console/page errors').toEqual([]);
});

test('fallback: server sent items but no nodes/edges -> client-derived graph (ghost carries project)', async ({ page }) => {
  await mockBackend(page, [], []);
  await page.goto('/index.html');
  await bootGraph(page);

  const hasProjectNode = await page.evaluate(() => window.nodes.some((n) => n.type === 'project'));
  const ghost = await page.evaluate(() => window.nodes.find((n) => n.id === 'canon_ghost1'));

  expect(hasProjectNode, 'derive fallback built project nodes').toBe(true);
  expect(ghost, 'derive fallback ghost-stubbed the dangling link').toBeTruthy();
  expect(ghost.project, 'derive-path ghost carries the owning item project').toBe('lattice');
});
