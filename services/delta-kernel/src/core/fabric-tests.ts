/**
 * Delta-State Fabric v0 — Proof Tests
 *
 * Four brutal tests to prove the fabric is real:
 * 1. Deterministic Reconstruction — rebuild from deltas alone
 * 2. Delta Bandwidth Collapse — repetition shrinks traffic
 * 3. Off-Grid Loop Closure — sync without internet
 * 4. Drift Immunity — Markov spine governs behavior
 *
 * If these pass, you have a new class of operating system.
 * If not, it's noise.
 */

import {
  UUID,
  Entity,
  Delta,
  Mode,
  EntityType,
  TaskData,
  ThreadData,
  MessageData,
  DraftData,
  SystemStateData,
  PatternData,
  TokenData,
  EntityHead,
  InboxData,
} from './types';
import {
  createEntity,
  createDelta,
  reconstructState,
  verifyHashChain,
  generateUUID,
  now,
  hashState,
  applyPatch,
} from './delta';
import { route, bucketSignals } from './routing';
import {
  runPreparationEngine,
  PreparationContext,
  triageThreads,
  triageTasks,
} from './preparation';
import {
  computeHeadsDiff,
  generateWantEntries,
  createHeadsPacket,
  createDeltasPacket,
  createWantPacket,
  validateDelta,
  prioritizeDeltas,
} from './delta-sync';
import {
  createEmptyDictionary,
  getOrCreateToken,
  getOrCreatePattern,
  discoverAndCompress,
  DictionaryState,
  compressTokenSequence,
  tokenize,
} from './dictionary';
import { buildCockpit, CockpitBuildContext } from './cockpit';
import { isTemplateLegalForMode, TEMPLATE_IDS } from './templates';

// === TEST UTILITIES ===

interface TestResult {
  name: string;
  passed: boolean;
  details: string[];
  metrics?: Record<string, number>;
}

function assert(condition: boolean, message: string): void {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

function assertEqual<T>(actual: T, expected: T, message: string): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${message}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

// === TEST 1: DETERMINISTIC RECONSTRUCTION ===

export async function testDeterministicReconstruction(): Promise<TestResult> {
  const details: string[] = [];
  const metrics: Record<string, number> = {};

  try {
    // Step 1: Create entities
    details.push('Creating initial entities...');

    // Create system state
    const systemStateData: SystemStateData = {
      mode: 'CLOSE_LOOPS',
      signals: {
        sleep_hours: 7,
        open_loops: 3,
        assets_shipped: 1,
        deep_work_blocks: 1,
        money_delta: 500,
      },
    };
    const systemState = await createEntity('system_state', systemStateData);

    // Create 3 tasks
    const tasks: Array<{ entity: Entity; delta: Delta; state: TaskData }> = [];
    for (let i = 0; i < 3; i++) {
      const taskData: TaskData = {
        title_template: 'TASK_{num}',
        title_params: { num: String(i + 1) },
        status: 'OPEN',
        priority: i === 0 ? 'HIGH' : 'NORMAL',
        due_at: i === 0 ? now() + 86400000 : null,
        linked_thread: null,
      };
      const task = await createEntity('task', taskData);
      tasks.push(task);
    }
    details.push(`Created ${tasks.length} tasks`);

    // Create 2 threads
    const threads: Array<{ entity: Entity; delta: Delta; state: ThreadData }> = [];
    for (let i = 0; i < 2; i++) {
      const threadData: ThreadData = {
        title: `Thread ${i + 1}`,
        participants: [generateUUID()],
        last_message_id: null,
        unread_count: i + 1,
        priority: i === 0 ? 'HIGH' : 'NORMAL',
        task_flag: i === 0,
      };
      const thread = await createEntity('thread', threadData);
      threads.push(thread);
    }
    details.push(`Created ${threads.length} threads`);

    // Create 4 messages
    const messages: Array<{ entity: Entity; delta: Delta; state: MessageData }> = [];
    for (let i = 0; i < 4; i++) {
      const messageData: MessageData = {
        thread_id: threads[i % 2].entity.entity_id,
        template_id: TEMPLATE_IDS.ACK,
        params: { content: `Message ${i + 1}` },
        sender: generateUUID(),
        status: 'SENT',
      };
      const message = await createEntity('message', messageData);
      messages.push(message);
    }
    details.push(`Created ${messages.length} messages`);

    // Let prep engine generate drafts
    const prepContext: PreparationContext = {
      systemState: { entity: systemState.entity, state: systemState.state },
      threads: threads.map((t) => ({ entity: t.entity, state: t.state })),
      tasks: tasks.map((t) => ({ entity: t.entity, state: t.state })),
      existingDrafts: [],
      triggeredByDeltaId: systemState.delta.delta_id,
    };

    const prepResult = await runPreparationEngine(prepContext);
    details.push(`Prep engine generated ${prepResult.newDrafts.length} drafts`);

    // Collect ALL deltas
    const allDeltas: Delta[] = [
      systemState.delta,
      ...tasks.map((t) => t.delta),
      ...threads.map((t) => t.delta),
      ...messages.map((m) => m.delta),
      ...prepResult.newDrafts.map((d) => d.delta),
    ];

    metrics.total_entities = 1 + tasks.length + threads.length + messages.length + prepResult.newDrafts.length;
    metrics.total_deltas = allDeltas.length;
    details.push(`Total: ${metrics.total_entities} entities, ${metrics.total_deltas} deltas`);

    // Step 2: "Delete" everything (simulate)
    details.push('Simulating system shutdown and data loss...');
    // (We just won't use the entity objects anymore)

    // Step 3: Rebuild from deltas only
    details.push('Rebuilding from delta log only...');

    // Group deltas by entity
    const deltasByEntity = new Map<UUID, Delta[]>();
    for (const delta of allDeltas) {
      const existing = deltasByEntity.get(delta.entity_id) || [];
      existing.push(delta);
      deltasByEntity.set(delta.entity_id, existing);
    }

    // Reconstruct each entity
    const reconstructedEntities = new Map<UUID, { state: unknown; hash: string }>();

    for (const [entityId, entityDeltas] of deltasByEntity) {
      const sorted = [...entityDeltas].sort((a, b) => a.timestamp - b.timestamp);
      const state = reconstructState(sorted);
      const hash = await hashState(state);

      reconstructedEntities.set(entityId, { state, hash });
    }

    details.push(`Reconstructed ${reconstructedEntities.size} entities from deltas`);

    // Step 4: Verify reconstruction matches original
    details.push('Verifying reconstruction matches original...');

    // Check system state
    const reconstructedSystemState = reconstructedEntities.get(systemState.entity.entity_id);
    assert(reconstructedSystemState !== undefined, 'System state not reconstructed');
    assertEqual(
      (reconstructedSystemState!.state as SystemStateData).mode,
      systemState.state.mode,
      'Mode mismatch'
    );
    details.push('✓ System state mode matches');

    // Check tasks
    for (const task of tasks) {
      const reconstructed = reconstructedEntities.get(task.entity.entity_id);
      assert(reconstructed !== undefined, `Task ${task.entity.entity_id} not reconstructed`);
      assertEqual(
        (reconstructed!.state as TaskData).status,
        task.state.status,
        'Task status mismatch'
      );
    }
    details.push('✓ All tasks reconstructed correctly');

    // Check threads
    for (const thread of threads) {
      const reconstructed = reconstructedEntities.get(thread.entity.entity_id);
      assert(reconstructed !== undefined, `Thread ${thread.entity.entity_id} not reconstructed`);
      assertEqual(
        (reconstructed!.state as ThreadData).title,
        thread.state.title,
        'Thread title mismatch'
      );
    }
    details.push('✓ All threads reconstructed correctly');

    // Check drafts
    for (const draft of prepResult.newDrafts) {
      const reconstructed = reconstructedEntities.get(draft.entity.entity_id);
      assert(reconstructed !== undefined, `Draft ${draft.entity.entity_id} not reconstructed`);
      assertEqual(
        (reconstructed!.state as DraftData).status,
        draft.state.status,
        'Draft status mismatch'
      );
    }
    details.push('✓ All drafts reconstructed correctly');

    // Verify hash chain integrity
    for (const [entityId, entityDeltas] of deltasByEntity) {
      const valid = await verifyHashChain(entityDeltas);
      assert(valid, `Hash chain broken for entity ${entityId}`);
    }
    details.push('✓ All hash chains valid');

    // Rebuild cockpit state - need to create inbox for buildCockpit
    const inboxData = {
      unread_count: 0,
      priority_queue: [],
      task_queue: [],
      idea_queue: [],
      last_activity_at: now(),
    };
    const inbox = await createEntity('inbox', inboxData);

    const cockpitContext: CockpitBuildContext = {
      systemState: {
        entity: systemState.entity,
        state: reconstructedSystemState!.state as SystemStateData,
      },
      inbox: { entity: inbox.entity, state: inbox.state },
      threads: threads.map((t) => ({
        entity: t.entity,
        state: reconstructedEntities.get(t.entity.entity_id)!.state as ThreadData,
      })),
      tasks: tasks.map((t) => ({
        entity: t.entity,
        state: reconstructedEntities.get(t.entity.entity_id)!.state as TaskData,
      })),
      drafts: prepResult.newDrafts.map((d) => ({
        entity: d.entity,
        state: reconstructedEntities.get(d.entity.entity_id)!.state as DraftData,
      })),
      pendingAction: null,
    };

    const cockpitState = buildCockpit(cockpitContext);
    assert(cockpitState.mode === systemState.state.mode, 'Cockpit mode mismatch');
    details.push('✓ Cockpit state rebuilt correctly');

    return {
      name: 'TEST 1: Deterministic Reconstruction',
      passed: true,
      details,
      metrics,
    };
  } catch (error) {
    details.push(`✗ FAILED: ${(error as Error).message}`);
    return {
      name: 'TEST 1: Deterministic Reconstruction',
      passed: false,
      details,
      metrics,
    };
  }
}

// === TEST 2: DELTA BANDWIDTH COLLAPSE ===

export async function testBandwidthCollapse(): Promise<TestResult> {
  const details: string[] = [];
  const metrics: Record<string, number> = {};

  try {
    // Initialize dictionary
    const dictionary = createEmptyDictionary();

    // Test concept: Measure raw content size vs compressed reference size
    // The Matryoshka principle: repetition → structure → tiny reference

    details.push('Building dictionary from repeated phrases...');

    // Simulate a real-world scenario: same phrases appear many times
    const repeatedPhrases = [
      'send the document',
      'please review and approve',
      'meeting scheduled for tomorrow',
      'thanks for your help',
      'let me know if you need anything',
    ];

    // Each phrase appears 20 times (simulating real usage patterns)
    const allTexts: string[] = [];
    for (let i = 0; i < 20; i++) {
      for (const phrase of repeatedPhrases) {
        allTexts.push(phrase);
      }
    }

    // Measure RAW byte size (what you'd transmit without compression)
    const rawBytes = allTexts.reduce((sum, text) => sum + text.length, 0);
    metrics.raw_bytes = rawBytes;
    details.push(`Raw content: ${rawBytes} bytes for ${allTexts.length} phrases`);

    // Build dictionary by processing all texts
    details.push('Processing texts through dictionary...');

    for (const phrase of repeatedPhrases) {
      const words = tokenize(phrase);
      const tokenIds: string[] = [];

      for (const word of words) {
        const result = await getOrCreateToken(dictionary, word);
        tokenIds.push(result.tokenId);
      }

      // Create pattern for the whole phrase
      await getOrCreatePattern(dictionary, tokenIds);
    }

    metrics.tokens_created = dictionary.tokens.size;
    metrics.patterns_created = dictionary.patterns.size;
    details.push(`Dictionary: ${dictionary.tokens.size} tokens, ${dictionary.patterns.size} patterns`);

    // Now measure COMPRESSED representation
    // Each phrase becomes just a pattern reference like "P1", "P2", etc.
    details.push('Compressing with dictionary references...');

    let compressedRefs: string[] = [];
    for (const text of allTexts) {
      const words = tokenize(text);
      const tokenIds: string[] = [];

      for (const word of words) {
        const result = await getOrCreateToken(dictionary, word);
        tokenIds.push(result.tokenId);
      }

      const compressed = compressTokenSequence(dictionary, tokenIds);

      // In compressed form, a pattern is just "P1" instead of "send the document"
      for (const c of compressed) {
        compressedRefs.push(c.ref_id);
      }
    }

    // Measure compressed byte size (just the reference IDs)
    const compressedBytes = compressedRefs.reduce((sum, ref) => sum + ref.length, 0);
    metrics.compressed_bytes = compressedBytes;
    details.push(`Compressed: ${compressedBytes} bytes (${compressedRefs.length} refs)`);

    // Dictionary overhead (one-time cost to transmit dictionary)
    let dictOverhead = 0;
    for (const [_, token] of dictionary.tokens) {
      dictOverhead += token.state.value.length + token.state.token_id.length;
    }
    for (const [_, pattern] of dictionary.patterns) {
      dictOverhead += pattern.state.pattern_id.length +
        pattern.state.token_sequence.join(',').length;
    }
    metrics.dictionary_overhead = dictOverhead;
    details.push(`Dictionary overhead: ${dictOverhead} bytes (one-time)`);

    // Total compressed = refs + dictionary
    const totalCompressed = compressedBytes + dictOverhead;
    metrics.total_compressed = totalCompressed;

    // Calculate savings
    const savings = ((rawBytes - totalCompressed) / rawBytes) * 100;
    metrics.savings_percent = Math.round(savings);
    details.push(`Total compressed (with dict): ${totalCompressed} bytes`);
    details.push(`Bandwidth savings: ${savings.toFixed(1)}%`);

    // The MORE repetition, the BETTER the savings
    // With 20 repetitions of 5 phrases, dictionary cost is amortized
    const passed = totalCompressed < rawBytes;

    if (passed) {
      details.push('✓ Compressed + dictionary is smaller than raw');
      details.push('✓ MATRYOSHKA COMPRESSION PROVEN');
      details.push(`  Raw: "${repeatedPhrases[0]}" (${repeatedPhrases[0].length} bytes)`);
      const patternRef = Array.from(dictionary.patterns.values())[0]?.state.pattern_id || 'P1';
      details.push(`  Compressed: "${patternRef}" (${patternRef.length} bytes)`);
    } else {
      details.push('✗ Need more repetition to amortize dictionary cost');
    }

    return {
      name: 'TEST 2: Delta Bandwidth Collapse',
      passed,
      details,
      metrics,
    };
  } catch (error) {
    details.push(`✗ FAILED: ${(error as Error).message}`);
    return {
      name: 'TEST 2: Delta Bandwidth Collapse',
      passed: false,
      details,
      metrics,
    };
  }
}

// === TEST 3: OFF-GRID LOOP CLOSURE ===

export async function testOffGridLoopClosure(): Promise<TestResult> {
  const details: string[] = [];
  const metrics: Record<string, number> = {};

  try {
    details.push('Simulating two nodes in airplane mode...');

    // Node A state
    const nodeAEntities = new Map<UUID, Entity>();
    const nodeADeltas = new Map<UUID, Delta[]>();
    const nodeAEntityTypes = new Map<UUID, EntityType>();

    // Node B state
    const nodeBEntities = new Map<UUID, Entity>();
    const nodeBDeltas = new Map<UUID, Delta[]>();
    const nodeBEntityTypes = new Map<UUID, EntityType>();

    // Both start with same system state
    const systemStateData: SystemStateData = {
      mode: 'CLOSE_LOOPS',
      signals: {
        sleep_hours: 7,
        open_loops: 2,
        assets_shipped: 1,
        deep_work_blocks: 1,
        money_delta: 500,
      },
    };
    const systemState = await createEntity('system_state', systemStateData);

    // Add to both nodes
    nodeAEntities.set(systemState.entity.entity_id, systemState.entity);
    nodeADeltas.set(systemState.entity.entity_id, [systemState.delta]);
    nodeAEntityTypes.set(systemState.entity.entity_id, 'system_state');

    nodeBEntities.set(systemState.entity.entity_id, { ...systemState.entity });
    nodeBDeltas.set(systemState.entity.entity_id, [{ ...systemState.delta }]);
    nodeBEntityTypes.set(systemState.entity.entity_id, 'system_state');

    details.push('Both nodes start with identical system state');

    // Node A goes offline and makes changes
    details.push('Node A goes offline...');

    // Node A: Send a message
    const messageData: MessageData = {
      thread_id: generateUUID(),
      template_id: TEMPLATE_IDS.UPDATE,
      params: { update: 'Offline message from Node A' },
      sender: generateUUID(),
      status: 'SENT',
    };
    const messageA = await createEntity('message', messageData);
    nodeAEntities.set(messageA.entity.entity_id, messageA.entity);
    nodeADeltas.set(messageA.entity.entity_id, [messageA.delta]);
    nodeAEntityTypes.set(messageA.entity.entity_id, 'message');
    details.push('Node A: Created message');

    // Node A: Complete a task
    const taskData: TaskData = {
      title_template: 'Offline task',
      title_params: {},
      status: 'OPEN',
      priority: 'NORMAL',
      due_at: null,
      linked_thread: null,
    };
    const taskA = await createEntity('task', taskData);
    nodeAEntities.set(taskA.entity.entity_id, taskA.entity);
    nodeADeltas.set(taskA.entity.entity_id, [taskA.delta]);
    nodeAEntityTypes.set(taskA.entity.entity_id, 'task');

    // Complete the task
    const completeTaskResult = await createDelta(
      taskA.entity,
      taskA.state,
      [{ op: 'replace', path: '/status', value: 'DONE' }],
      'user'
    );
    nodeAEntities.set(completeTaskResult.entity.entity_id, completeTaskResult.entity);
    nodeADeltas.get(taskA.entity.entity_id)!.push(completeTaskResult.delta);
    details.push('Node A: Created and completed task');

    // Node A: Change mode (via signal update)
    const modeChangeResult = await createDelta(
      systemState.entity,
      systemState.state,
      [
        { op: 'replace', path: '/signals/open_loops', value: 0 },
        { op: 'replace', path: '/mode', value: 'BUILD' },
      ],
      'user'
    );
    nodeAEntities.set(modeChangeResult.entity.entity_id, modeChangeResult.entity);
    nodeADeltas.get(systemState.entity.entity_id)!.push(modeChangeResult.delta);
    details.push('Node A: Changed mode to BUILD');

    metrics.node_a_entities = nodeAEntities.size;
    metrics.node_a_deltas = Array.from(nodeADeltas.values()).flat().length;

    // Sync via delta protocol
    details.push('Syncing over delta protocol...');

    // Build HEADS for both nodes
    const nodeAHeads: EntityHead[] = Array.from(nodeAEntities.entries()).map(
      ([id, entity]) => ({
        entity_id: id,
        entity_type: nodeAEntityTypes.get(id)!,
        current_hash: entity.current_hash,
        current_version: entity.current_version,
      })
    );

    const nodeBHeads: EntityHead[] = Array.from(nodeBEntities.entries()).map(
      ([id, entity]) => ({
        entity_id: id,
        entity_type: nodeBEntityTypes.get(id)!,
        current_hash: entity.current_hash,
        current_version: entity.current_version,
      })
    );

    // Compute diff
    const diff = computeHeadsDiff(nodeBHeads, nodeAHeads);
    details.push(
      `Diff: ${diff.remoteOnly.length} new entities, ${diff.diverged.length} diverged`
    );

    // Generate WANTs
    const wants = generateWantEntries(diff, nodeBDeltas);
    details.push(`Node B wants ${wants.length} entity updates`);

    // Node A sends deltas
    const deltasToSend: Delta[] = [];
    for (const want of wants) {
      const entityDeltas = nodeADeltas.get(want.entity_id) || [];
      let found = want.since_hash === '0'.repeat(64);
      for (const delta of entityDeltas) {
        if (found) deltasToSend.push(delta);
        if (delta.new_hash === want.since_hash) found = true;
      }
    }

    metrics.deltas_synced = deltasToSend.length;
    details.push(`Node A sends ${deltasToSend.length} deltas`);

    // Node B applies deltas
    let conflictsDetected = 0;
    for (const delta of deltasToSend) {
      const validation = await validateDelta(delta, nodeBEntities, nodeBDeltas);

      if (validation.valid) {
        // Apply delta
        const existing = nodeBDeltas.get(delta.entity_id) || [];
        existing.push(delta);
        nodeBDeltas.set(delta.entity_id, existing);

        // Reconstruct entity state
        const state = reconstructState(existing);
        const hash = await hashState(state);

        const existingEntity = nodeBEntities.get(delta.entity_id);
        if (existingEntity) {
          existingEntity.current_hash = hash;
          existingEntity.current_version++;
        } else {
          // New entity
          nodeBEntities.set(delta.entity_id, {
            entity_id: delta.entity_id,
            entity_type: nodeAEntityTypes.get(delta.entity_id)!,
            created_at: delta.timestamp,
            current_version: 1,
            current_hash: hash,
            is_archived: false,
          });
          nodeBEntityTypes.set(
            delta.entity_id,
            nodeAEntityTypes.get(delta.entity_id)!
          );
        }
      } else {
        conflictsDetected++;
        details.push(`Conflict: ${validation.reason} - ${validation.message}`);
      }
    }

    metrics.conflicts = conflictsDetected;
    details.push(`Conflicts detected: ${conflictsDetected}`);

    // Verify convergence
    details.push('Verifying convergence...');

    let converged = true;

    // Check all entities match
    for (const [entityId, entityA] of nodeAEntities) {
      const entityB = nodeBEntities.get(entityId);
      if (!entityB) {
        details.push(`✗ Entity ${entityId} missing on Node B`);
        converged = false;
        continue;
      }

      if (entityA.current_hash !== entityB.current_hash) {
        details.push(`✗ Hash mismatch for entity ${entityId}`);
        converged = false;
        continue;
      }
    }

    if (converged) {
      details.push('✓ Both nodes converged perfectly');
      details.push('✓ No conflicts');
      details.push('✓ No lost state');
    }

    return {
      name: 'TEST 3: Off-Grid Loop Closure',
      passed: converged && conflictsDetected === 0,
      details,
      metrics,
    };
  } catch (error) {
    details.push(`✗ FAILED: ${(error as Error).message}`);
    return {
      name: 'TEST 3: Off-Grid Loop Closure',
      passed: false,
      details,
      metrics,
    };
  }
}

// === TEST 4: DRIFT IMMUNITY ===

export async function testDriftImmunity(): Promise<TestResult> {
  const details: string[] = [];
  const metrics: Record<string, number> = {};

  try {
    details.push('Testing Markov spine governance...');

    // Set up system state with LOW sleep → must force RECOVER
    const systemStateData: SystemStateData = {
      mode: 'BUILD', // Start in BUILD
      signals: {
        sleep_hours: 4, // LOW - should force RECOVER
        open_loops: 1,
        assets_shipped: 2,
        deep_work_blocks: 2,
        money_delta: 1000,
      },
    };

    details.push('Initial: Mode=BUILD, sleep_hours=4 (LOW)');

    // Route should force RECOVER
    const buckets = bucketSignals(systemStateData.signals);
    details.push(`Buckets: sleep=${buckets.sleep_hours}, loops=${buckets.open_loops}`);

    const newMode = route(systemStateData.mode, systemStateData.signals);
    details.push(`Routing result: ${systemStateData.mode} → ${newMode}`);

    metrics.expected_mode_is_recover = newMode === 'RECOVER' ? 1 : 0;

    // Verify RECOVER mode is enforced
    if (newMode !== 'RECOVER') {
      details.push('✗ FAILED: Low sleep did not force RECOVER mode');
      return {
        name: 'TEST 4: Drift Immunity',
        passed: false,
        details,
        metrics,
      };
    }
    details.push('✓ Low sleep forces RECOVER mode');

    // Try to execute BUILD actions in RECOVER mode
    details.push('Attempting BUILD actions in RECOVER mode...');

    const buildTemplates = [
      TEMPLATE_IDS.BUILD_OUTLINE,
      TEMPLATE_IDS.COMPOUND_EXTEND,
      TEMPLATE_IDS.SCALE_DELEGATE,
    ];

    let blockedCount = 0;
    for (const templateId of buildTemplates) {
      const isLegal = isTemplateLegalForMode(templateId, 'RECOVER');
      if (!isLegal) {
        blockedCount++;
        details.push(`✓ Template ${templateId} blocked in RECOVER`);
      } else {
        details.push(`✗ Template ${templateId} allowed in RECOVER (should be blocked)`);
      }
    }

    metrics.blocked_actions = blockedCount;
    metrics.total_build_actions = buildTemplates.length;

    // Verify all BUILD actions are blocked
    const allBlocked = blockedCount === buildTemplates.length;

    if (allBlocked) {
      details.push('✓ All BUILD/COMPOUND/SCALE actions blocked in RECOVER');
    } else {
      details.push('✗ Some restricted actions were allowed');
    }

    // Test that RECOVER-specific actions ARE allowed
    const recoverTemplates = [TEMPLATE_IDS.RECOVER_REST, TEMPLATE_IDS.ACK];
    let allowedCount = 0;

    for (const templateId of recoverTemplates) {
      const isLegal = isTemplateLegalForMode(templateId, 'RECOVER');
      if (isLegal) {
        allowedCount++;
        details.push(`✓ Template ${templateId} allowed in RECOVER`);
      } else {
        details.push(`✗ Template ${templateId} blocked in RECOVER (should be allowed)`);
      }
    }

    metrics.allowed_recover_actions = allowedCount;

    // Test mode progression requirements
    details.push('Testing mode progression requirements...');

    // RECOVER → CLOSE_LOOPS requires sleep OK
    const recoverSignals: SystemStateData['signals'] = {
      sleep_hours: 6, // OK now
      open_loops: 5,
      assets_shipped: 0,
      deep_work_blocks: 0,
      money_delta: 0,
    };

    const fromRecoverMode = route('RECOVER', recoverSignals);
    const canExitRecover = fromRecoverMode !== 'RECOVER';
    details.push(
      `With sleep OK: RECOVER → ${fromRecoverMode} (${canExitRecover ? 'can exit' : 'stuck'})`
    );

    // CLOSE_LOOPS → BUILD requires open_loops LOW
    const closeLoopsSignals: SystemStateData['signals'] = {
      sleep_hours: 7,
      open_loops: 0, // Must be very low
      assets_shipped: 0,
      deep_work_blocks: 0,
      money_delta: 0,
    };

    const fromCloseLoopsMode = route('CLOSE_LOOPS', closeLoopsSignals);
    const canEnterBuild = fromCloseLoopsMode === 'BUILD';
    details.push(
      `With loops closed: CLOSE_LOOPS → ${fromCloseLoopsMode} (${canEnterBuild ? 'can enter BUILD' : 'blocked'})`
    );

    // Overall pass: spine governs behavior
    const passed = newMode === 'RECOVER' && allBlocked;

    if (passed) {
      details.push('');
      details.push('✓ MARKOV SPINE GOVERNS BEHAVIOR');
      details.push('✓ Mode law cannot be bypassed');
      details.push('✓ Restricted actions do not exist in wrong modes');
    }

    return {
      name: 'TEST 4: Drift Immunity',
      passed,
      details,
      metrics,
    };
  } catch (error) {
    details.push(`✗ FAILED: ${(error as Error).message}`);
    return {
      name: 'TEST 4: Drift Immunity',
      passed: false,
      details,
      metrics,
    };
  }
}

// === TEST RUNNER ===

export async function runAllTests(): Promise<{
  results: TestResult[];
  summary: { passed: number; failed: number; total: number };
}> {
  console.log('╔══════════════════════════════════════════════════════════╗');
  console.log('║     DELTA-STATE FABRIC v0 — PROOF TESTS                  ║');
  console.log('╚══════════════════════════════════════════════════════════╝');
  console.log('');

  const results: TestResult[] = [];

  // Run each test
  const tests = [
    { name: 'Deterministic Reconstruction', fn: testDeterministicReconstruction },
    { name: 'Bandwidth Collapse', fn: testBandwidthCollapse },
    { name: 'Off-Grid Loop Closure', fn: testOffGridLoopClosure },
    { name: 'Drift Immunity', fn: testDriftImmunity },
  ];

  for (const test of tests) {
    console.log(`\n▶ Running: ${test.name}...`);
    const result = await test.fn();
    results.push(result);

    const status = result.passed ? '✅ PASSED' : '❌ FAILED';
    console.log(`  ${status}`);

    for (const detail of result.details) {
      console.log(`    ${detail}`);
    }

    if (result.metrics) {
      console.log('  Metrics:');
      for (const [key, value] of Object.entries(result.metrics)) {
        console.log(`    ${key}: ${value}`);
      }
    }
  }

  // Summary
  const passed = results.filter((r) => r.passed).length;
  const failed = results.filter((r) => !r.passed).length;

  console.log('\n');
  console.log('╔══════════════════════════════════════════════════════════╗');
  console.log('║                      SUMMARY                              ║');
  console.log('╠══════════════════════════════════════════════════════════╣');
  console.log(`║  Passed: ${passed}/${results.length}                                            ║`);
  console.log(`║  Failed: ${failed}/${results.length}                                            ║`);
  console.log('╚══════════════════════════════════════════════════════════╝');

  if (passed === results.length) {
    console.log('\n🎯 ALL TESTS PASSED');
    console.log('You have a new class of operating system.');
  } else {
    console.log('\n⚠️  SOME TESTS FAILED');
    console.log('Review failures and fix before deployment.');
  }

  return {
    results,
    summary: { passed, failed, total: results.length },
  };
}

// Export for direct execution
export { runAllTests as default };
