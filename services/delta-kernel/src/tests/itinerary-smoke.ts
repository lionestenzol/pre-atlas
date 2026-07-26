/**
 * Itinerary smoke — proves buildItinerary composes the six ordering rules
 * and emits close_via verbs. Run: npx tsx src/tests/itinerary-smoke.ts
 */

import { buildItinerary, parseOpenLoops, type ItineraryBuildContext } from '../api/itinerary';
import type { Entity, SystemStateData, PendingActionData, TaskData } from '../core/types-core';

function entity(id: string, type: Entity['entity_type']): Entity {
  return {
    entity_id: id,
    entity_type: type,
    created_at: Date.now(),
    current_version: 1,
    current_hash: 'x'.repeat(64),
    is_archived: false,
  };
}

function pending(id: string, action_type: PendingActionData['action_type']): { entity: Entity; state: PendingActionData } {
  return {
    entity: entity(id, 'pending_action'),
    state: {
      action_type,
      target_entity_id: 'target-1',
      payload: {},
      status: 'PENDING',
      created_at: Date.now(),
      expires_at: Date.now() + 30 * 60 * 1000,
      confirmed_at: null,
    },
  };
}

function task(id: string, title: string, priority: TaskData['priority'], status: TaskData['status'] = 'OPEN', linked_thread: string | null = null): { entity: Entity; state: TaskData } {
  return {
    entity: entity(id, 'task'),
    state: {
      title_template: title,
      title_params: {},
      status,
      priority,
      due_at: null,
      linked_thread,
    },
  };
}

function systemState(mode: SystemStateData['mode']): { entity: Entity; state: SystemStateData } {
  return {
    entity: entity('sys-1', 'system_state'),
    state: {
      mode,
      last_mode_transition_at: Date.now() - 3600_000,
      signals: {
        sleep_hours: 7,
        open_loops: 2,
        assets_shipped: 1,
        deep_work_blocks: 2,
        money_delta: 0,
      },
    },
  };
}

let failures = 0;
function assert(cond: boolean, label: string) {
  if (cond) {
    process.stdout.write(`  ✓ ${label}\n`);
  } else {
    process.stdout.write(`  ✗ ${label}\n`);
    failures++;
  }
}

process.stdout.write('itinerary-smoke\n');

// Test 1: pending action comes first
{
  const ctx: ItineraryBuildContext = {
    systemState: systemState('BUILD'),
    pendingActions: [pending('p1', 'complete_task')],
    openLoops: [{ loop_id: 'L1', loop_title: 'Close the audit' }],
    tasks: [task('t1', 'Ship widget', 'HIGH')],
    directive: null,
  };
  const it = buildItinerary(ctx);
  assert(it.blocks.length === 3, 'composes 3 blocks (pending + loop + task)');
  assert(it.blocks[0].kind === 'pending_action', 'pending action first');
  assert(it.blocks[0].close_via.method === 'POST', 'pending close_via is POST');
  assert(it.blocks[0].close_via.path.includes('/api/actions/confirm/'), 'pending close_via routes to confirm');
  assert(it.counts.total_composed === 3, 'counts.total_composed matches');
  assert(it.next?.kind === 'pending_action', 'next points at pending');
}

// Test 2: CLOSURE mode promotes open loops above tasks
{
  const ctx: ItineraryBuildContext = {
    systemState: systemState('CLOSURE'),
    pendingActions: [],
    openLoops: [{ loop_id: 'L1', loop_title: 'Close audit' }],
    tasks: [task('t1', 'Ship widget', 'HIGH')],
    directive: null,
  };
  const it = buildItinerary(ctx);
  assert(it.blocks[0].kind === 'open_loop', 'CLOSURE mode: open_loop first');
  assert(it.blocks[1].kind === 'task', 'CLOSURE mode: task second');
}

// Test 3: BUILD mode puts HIGH-priority tasks above open loops
{
  const ctx: ItineraryBuildContext = {
    systemState: systemState('BUILD'),
    pendingActions: [],
    openLoops: [{ loop_id: 'L1', loop_title: 'Close audit' }],
    tasks: [task('t1', 'Ship widget', 'HIGH')],
    directive: null,
  };
  const it = buildItinerary(ctx);
  assert(it.blocks[0].kind === 'task' && it.blocks[0].priority === 'HIGH', 'BUILD mode: HIGH task first');
  assert(it.blocks[1].kind === 'open_loop', 'BUILD mode: open_loop after HIGH tasks');
}

// Test 4: task close_via emits PUT with JSON-Patch body
{
  const ctx: ItineraryBuildContext = {
    systemState: systemState('BUILD'),
    pendingActions: [],
    openLoops: [],
    tasks: [task('t1', 'Do it', 'NORMAL')],
    directive: null,
  };
  const it = buildItinerary(ctx);
  const t = it.blocks[0];
  assert(t.close_via.method === 'PUT', 'task close_via is PUT');
  assert(Array.isArray(t.close_via.body) && (t.close_via.body as unknown[]).length === 1, 'task close_via body is JSON-Patch array');
}

// Test 5: loop close_via emits POST close_loop with full body
{
  const ctx: ItineraryBuildContext = {
    systemState: systemState('CLOSURE'),
    pendingActions: [],
    openLoops: [{ loop_id: 'L1', loop_title: 'X' }],
    tasks: [],
    directive: null,
  };
  const it = buildItinerary(ctx);
  const l = it.blocks[0];
  assert(l.close_via.path === '/api/law/close_loop', 'loop close_via path is close_loop');
  const body = l.close_via.body as Record<string, unknown>;
  assert(body?.loop_id === 'L1' && body?.outcome === 'closed', 'loop close_via body carries loop_id + outcome=closed');
}

// Test 6: limit is respected
{
  const tasks = Array.from({ length: 20 }, (_, i) => task(`t${i}`, `T${i}`, 'NORMAL'));
  const ctx: ItineraryBuildContext = {
    systemState: systemState('BUILD'),
    pendingActions: [],
    openLoops: [],
    tasks,
    directive: null,
    limit: 5,
  };
  const it = buildItinerary(ctx);
  assert(it.blocks.length === 5, 'limit=5 respected');
  assert(it.counts.tasks === 20, 'counts.tasks reports total, not composed');
}

// Test 7: parseOpenLoops handles varied shapes
{
  const gov = {
    open_loops: [
      { loop_id: 'a1', title: 'From loop_id + title' },
      { id: 'b2', loop_title: 'From id + loop_title' },
      { convo_id: 'c3' },
      { garbage: true },
      null,
      'not an object',
    ],
  };
  const parsed = parseOpenLoops(gov);
  assert(parsed.length === 3, 'parseOpenLoops keeps 3 valid, drops 3 malformed');
  assert(parsed[0].loop_id === 'a1' && parsed[0].loop_title === 'From loop_id + title', 'parseOpenLoops reads title');
  assert(parsed[2].loop_id === 'c3' && parsed[2].loop_title === undefined, 'parseOpenLoops tolerates missing title');
}

// Test 8: DONE tasks are excluded
{
  const ctx: ItineraryBuildContext = {
    systemState: systemState('BUILD'),
    pendingActions: [],
    openLoops: [],
    tasks: [task('t1', 'Done', 'HIGH', 'DONE'), task('t2', 'Open', 'HIGH', 'OPEN')],
    directive: null,
  };
  const it = buildItinerary(ctx);
  assert(it.blocks.length === 1 && it.blocks[0].source.task_id === 't2', 'DONE task filtered out');
  assert(it.counts.tasks === 1, 'counts.tasks excludes DONE');
}

process.stdout.write(failures === 0 ? '\nALL PASS\n' : `\n${failures} FAILURES\n`);
process.exit(failures === 0 ? 0 : 1);
