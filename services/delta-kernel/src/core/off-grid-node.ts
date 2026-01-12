/**
 * Delta-State Fabric — Module 7: Off-Grid Nodes
 *
 * Minimal hardware runtime for physical deployment on radios,
 * batteries, solar, and mesh networks.
 *
 * Node Classes:
 * - CORE: Full cockpit + prep + vector + AI
 * - EDGE: Cockpit shell + sync + radio
 * - MICRO: Radio + message/task shell only
 *
 * This is what turns Delta Fabric into an infrastructure organism.
 */

import {
  UUID,
  Timestamp,
  Mode,
  Entity,
  Delta,
  EntityType,
  TaskStatus,
  DraftType,
  DraftStatus,
  PendingActionStatus,
  NodeClass,
  HardwareProfile,
  RuntimeCapabilities,
  NodeRuntimeConfig,
  PowerState,
  CockpitShellState,
  ShellAction,
  ShellTaskItem,
  ShellDraftItem,
  RadioBurstPhase,
  RadioBurstSession,
  StorageBudget,
  SyncNode,
  SyncPacket,
  NODE_CAPABILITIES,
  STORAGE_LIMITS,
  SUPPORTED_ENTITY_TYPES,
  TaskData,
  DraftData,
  PendingActionData,
  SystemStateData,
} from './types';
import { generateUUID, now } from './delta';
import {
  createNode,
  createHelloPacket,
  createHeadsPacket,
  createWantPacket,
  createDeltasPacket,
  createAckPacket,
  computeHeadsDiff,
  generateWantEntries,
  prioritizeDeltas,
} from './delta-sync';
import { LeverageMove } from './preparation';

// === CONSTANTS ===

const IDLE_TIMEOUT_MS = 30000; // 30 seconds to idle
const DEEP_SLEEP_TIMEOUT_MS = 300000; // 5 minutes to deep sleep
const DEFAULT_WAKE_INTERVAL_MS = 3600000; // 1 hour periodic wake
const MAX_SHELL_ACTIONS = 7;
const MAX_SHELL_TASKS = 5;
const MAX_SHELL_DRAFTS = 3;

// === HARDWARE PROFILES ===

export const HARDWARE_PROFILES: Record<string, HardwareProfile> = {
  // CORE class hardware
  raspberry_pi_4: {
    cpu_class: 'full',
    storage_mb: 32000,
    has_display: true,
    display_type: 'full',
    has_radio: true,
    radio_type: 'multi',
    battery_powered: false,
    solar_capable: true,
  },
  laptop: {
    cpu_class: 'full',
    storage_mb: 256000,
    has_display: true,
    display_type: 'full',
    has_radio: true,
    radio_type: 'wifi',
    battery_powered: true,
    solar_capable: false,
  },

  // EDGE class hardware
  raspberry_pi_zero: {
    cpu_class: 'embedded',
    storage_mb: 8000,
    has_display: true,
    display_type: 'lcd_grid',
    has_radio: true,
    radio_type: 'lora',
    battery_powered: true,
    solar_capable: true,
  },
  esp32_lora: {
    cpu_class: 'embedded',
    storage_mb: 64,
    has_display: true,
    display_type: 'lcd_grid',
    has_radio: true,
    radio_type: 'lora',
    battery_powered: true,
    solar_capable: true,
  },
  old_android: {
    cpu_class: 'embedded',
    storage_mb: 2000,
    has_display: true,
    display_type: 'full',
    has_radio: true,
    radio_type: 'multi',
    battery_powered: true,
    solar_capable: true,
  },

  // MICRO class hardware
  esp8266: {
    cpu_class: 'micro',
    storage_mb: 4,
    has_display: false,
    display_type: 'none',
    has_radio: true,
    radio_type: 'lora',
    battery_powered: true,
    solar_capable: true,
  },
  rp2040_lora: {
    cpu_class: 'micro',
    storage_mb: 2,
    has_display: true,
    display_type: 'lcd_4line',
    has_radio: true,
    radio_type: 'lora',
    battery_powered: true,
    solar_capable: true,
  },
};

// === NODE CREATION ===

export function createNodeRuntime(
  nodeClass: NodeClass,
  hardwareProfile: HardwareProfile
): NodeRuntimeConfig {
  return {
    node_class: nodeClass,
    hardware: hardwareProfile,
    capabilities: NODE_CAPABILITIES[nodeClass],
    power_state: 'ACTIVE',
    wake_on_radio: true,
    wake_on_timer: nodeClass !== 'CORE', // CORE stays awake
    wake_interval_ms: nodeClass === 'MICRO' ? DEFAULT_WAKE_INTERVAL_MS : null,
    last_activity_at: now(),
    uptime_ms: 0,
  };
}

export function createCoreNode(hardware?: HardwareProfile): NodeRuntimeConfig {
  return createNodeRuntime('CORE', hardware || HARDWARE_PROFILES.raspberry_pi_4);
}

export function createEdgeNode(hardware?: HardwareProfile): NodeRuntimeConfig {
  return createNodeRuntime('EDGE', hardware || HARDWARE_PROFILES.esp32_lora);
}

export function createMicroNode(hardware?: HardwareProfile): NodeRuntimeConfig {
  return createNodeRuntime('MICRO', hardware || HARDWARE_PROFILES.esp8266);
}

// === POWER MANAGEMENT ===

export function updatePowerState(
  config: NodeRuntimeConfig,
  currentTime: Timestamp
): NodeRuntimeConfig {
  const idleTime = currentTime - config.last_activity_at;

  let newPowerState: PowerState = config.power_state;

  // Don't change state if in radio burst or charging
  if (config.power_state === 'RADIO_BURST' || config.power_state === 'CHARGING') {
    return config;
  }

  // Transition based on idle time
  if (idleTime > DEEP_SLEEP_TIMEOUT_MS && config.hardware.battery_powered) {
    newPowerState = 'DEEP_SLEEP';
  } else if (idleTime > IDLE_TIMEOUT_MS) {
    newPowerState = 'IDLE';
  } else {
    newPowerState = 'ACTIVE';
  }

  return {
    ...config,
    power_state: newPowerState,
    uptime_ms: config.uptime_ms + (currentTime - config.last_activity_at),
  };
}

export function wakeNode(config: NodeRuntimeConfig, reason: 'radio' | 'timer' | 'user'): NodeRuntimeConfig {
  return {
    ...config,
    power_state: reason === 'radio' ? 'RADIO_BURST' : 'ACTIVE',
    last_activity_at: now(),
  };
}

export function enterDeepSleep(config: NodeRuntimeConfig): NodeRuntimeConfig {
  if (!config.hardware.battery_powered) {
    return config; // Non-battery nodes don't deep sleep
  }

  return {
    ...config,
    power_state: 'DEEP_SLEEP',
  };
}

export function shouldWake(config: NodeRuntimeConfig, currentTime: Timestamp): boolean {
  if (config.power_state !== 'DEEP_SLEEP') return false;

  // Check timer wake
  if (config.wake_on_timer && config.wake_interval_ms) {
    const sleepTime = currentTime - config.last_activity_at;
    if (sleepTime >= config.wake_interval_ms) {
      return true;
    }
  }

  return false;
}

// === STORAGE MANAGEMENT ===

export function calculateStorageBudget(
  nodeClass: NodeClass,
  entities: Entity[],
  deltas: Delta[],
  storageMb: number
): StorageBudget {
  const totalBytes = storageMb * 1024 * 1024;

  // Estimate sizes (rough JSON sizes)
  const entitiesBytes = entities.length * 200; // ~200 bytes per entity
  const deltasBytes = deltas.reduce((sum, d) => sum + JSON.stringify(d).length, 0);
  const watermarksBytes = 1000; // Fixed overhead
  const conflictsBytes = 500; // Fixed overhead
  const lutBytes = 5000; // LUT tables

  const usedBytes = entitiesBytes + deltasBytes + watermarksBytes + conflictsBytes + lutBytes;

  return {
    total_bytes: totalBytes,
    entities_bytes: entitiesBytes,
    deltas_bytes: deltasBytes,
    watermarks_bytes: watermarksBytes,
    conflicts_bytes: conflictsBytes,
    lut_bytes: lutBytes,
    available_bytes: Math.max(0, totalBytes - usedBytes),
  };
}

export function isStorageAvailable(
  nodeClass: NodeClass,
  currentEntities: number,
  currentDeltas: number
): boolean {
  const limits = STORAGE_LIMITS[nodeClass];
  return currentEntities < limits.max_entities && currentDeltas < limits.max_deltas;
}

export function canStoreEntityType(nodeClass: NodeClass, entityType: EntityType): boolean {
  return SUPPORTED_ENTITY_TYPES[nodeClass].includes(entityType);
}

// === COCKPIT SHELL ===

export function createCockpitShellState(
  mode: Mode,
  tasks: Array<{ entity: Entity; state: TaskData }>,
  drafts: Array<{ entity: Entity; state: DraftData }>,
  pendingActions: Array<{ entity: Entity; state: PendingActionData }>,
  leverageMove: LeverageMove | null
): CockpitShellState {
  const currentTime = now();

  // Build visible tasks (top N by priority/overdue)
  const visibleTasks: ShellTaskItem[] = tasks
    .filter((t) => t.state.status === 'OPEN')
    .sort((a, b) => {
      // Overdue first
      const aOverdue = a.state.due_at && a.state.due_at < currentTime;
      const bOverdue = b.state.due_at && b.state.due_at < currentTime;
      if (aOverdue !== bOverdue) return aOverdue ? -1 : 1;
      // Then by priority
      const priorityOrder = { HIGH: 0, NORMAL: 1, LOW: 2 };
      return priorityOrder[a.state.priority] - priorityOrder[b.state.priority];
    })
    .slice(0, MAX_SHELL_TASKS)
    .map((t) => ({
      entity_id: t.entity.entity_id,
      title: renderTaskTitle(t.state),
      status: t.state.status,
      priority_indicator: t.state.priority === 'HIGH' ? '!' : '',
      is_overdue: !!(t.state.due_at && t.state.due_at < currentTime),
    }));

  // Build visible drafts
  const visibleDrafts: ShellDraftItem[] = drafts
    .filter((d) => d.state.status === 'READY')
    .slice(0, MAX_SHELL_DRAFTS)
    .map((d) => ({
      entity_id: d.entity.entity_id,
      summary: renderDraftSummary(d.state),
      draft_type: d.state.draft_type,
      is_expired: !!(d.state.expires_at && d.state.expires_at < currentTime),
    }));

  // Build actions list
  const actions: ShellAction[] = [];
  let actionIndex = 1;

  // Add draft apply actions
  for (const draft of visibleDrafts) {
    if (actionIndex > MAX_SHELL_ACTIONS) break;
    actions.push({
      index: actionIndex++,
      action_type: 'apply_draft',
      label: `Apply: ${draft.summary}`,
      target_entity_id: draft.entity_id,
      requires_confirm: true,
    });
  }

  // Add pending action confirmations
  for (const action of pendingActions.filter((a) => a.state.status === 'PENDING')) {
    if (actionIndex > MAX_SHELL_ACTIONS) break;
    actions.push({
      index: actionIndex++,
      action_type: 'confirm_action',
      label: `Confirm: ${action.state.action_type}`,
      target_entity_id: action.entity.entity_id,
      requires_confirm: true,
    });
  }

  // Add task complete actions
  for (const task of visibleTasks.slice(0, MAX_SHELL_ACTIONS - actions.length)) {
    if (actionIndex > MAX_SHELL_ACTIONS) break;
    actions.push({
      index: actionIndex++,
      action_type: 'complete_task',
      label: `Complete: ${task.title}`,
      target_entity_id: task.entity_id,
      requires_confirm: false,
    });
  }

  return {
    mode_display: mode,
    selected_index: 0,
    visible_actions: actions,
    visible_tasks: visibleTasks,
    visible_drafts: visibleDrafts,
    leverage_hint: leverageMove?.title || null,
    status_line: `${actions.length} actions | ${visibleTasks.length} tasks`,
    last_refresh_at: currentTime,
  };
}

function renderTaskTitle(task: TaskData): string {
  // Simple template rendering
  let title = task.title_template;
  for (const [key, value] of Object.entries(task.title_params)) {
    title = title.replace(`{${key}}`, value);
  }
  return title.slice(0, 30); // Truncate for shell display
}

function renderDraftSummary(draft: DraftData): string {
  return `${draft.draft_type}: ${draft.template_id}`.slice(0, 25);
}

export function renderCockpitShell(state: CockpitShellState): string {
  const lines: string[] = [];

  // Header
  lines.push(`MODE: ${state.mode_display}`);
  lines.push('');

  // Actions
  lines.push('ACTIONS:');
  for (const action of state.visible_actions) {
    const marker = state.selected_index === action.index ? '>' : ' ';
    lines.push(`${marker}[${action.index}] ${action.label}`);
  }
  lines.push('');

  // Tasks
  lines.push('TASKS:');
  for (const task of state.visible_tasks) {
    const overdue = task.is_overdue ? '*' : ' ';
    const priority = task.priority_indicator;
    lines.push(`${overdue}${priority} ${task.title}`);
  }
  lines.push('');

  // Drafts
  if (state.visible_drafts.length > 0) {
    lines.push('DRAFTS:');
    for (const draft of state.visible_drafts) {
      const expired = draft.is_expired ? '(exp)' : '';
      lines.push(`  • ${draft.summary} ${expired}`);
    }
    lines.push('');
  }

  // Leverage hint
  if (state.leverage_hint) {
    lines.push('LEVERAGE:');
    lines.push(`  • ${state.leverage_hint}`);
    lines.push('');
  }

  // Status line
  lines.push('---');
  lines.push(state.status_line);

  return lines.join('\n');
}

// Keypad input handling
export type ShellInput = '1' | '2' | '3' | '4' | '5' | '6' | '7' | 'Y' | 'N' | 'UP' | 'DOWN';

export interface ShellInputResult {
  action: ShellAction | null;
  confirmed: boolean;
  newState: CockpitShellState;
}

export function handleShellInput(
  state: CockpitShellState,
  input: ShellInput
): ShellInputResult {
  let newState = { ...state };
  let action: ShellAction | null = null;
  let confirmed = false;

  switch (input) {
    case '1':
    case '2':
    case '3':
    case '4':
    case '5':
    case '6':
    case '7':
      const index = parseInt(input);
      const selectedAction = state.visible_actions.find((a) => a.index === index);
      if (selectedAction) {
        newState.selected_index = index;
        if (!selectedAction.requires_confirm) {
          action = selectedAction;
          confirmed = true;
        }
      }
      break;

    case 'Y':
      const currentAction = state.visible_actions.find((a) => a.index === state.selected_index);
      if (currentAction) {
        action = currentAction;
        confirmed = true;
      }
      break;

    case 'N':
      newState.selected_index = 0;
      break;

    case 'UP':
      if (newState.selected_index > 1) {
        newState.selected_index--;
      }
      break;

    case 'DOWN':
      if (newState.selected_index < state.visible_actions.length) {
        newState.selected_index++;
      }
      break;
  }

  return { action, confirmed, newState };
}

// === RADIO BURST PROFILE ===

export function createRadioBurstSession(localNodeId: UUID): RadioBurstSession {
  return {
    session_id: generateUUID(),
    peer_node_id: null,
    phase: 'IDLE',
    started_at: now(),
    packets_sent: 0,
    packets_received: 0,
    bytes_transmitted: 0,
    rssi: null,
    snr: null,
  };
}

export function advanceBurstPhase(session: RadioBurstSession): RadioBurstPhase {
  const phaseOrder: RadioBurstPhase[] = ['IDLE', 'HELLO', 'HEADS', 'WANT', 'DELTAS', 'ACK', 'COMPLETE'];
  const currentIndex = phaseOrder.indexOf(session.phase);

  if (currentIndex < phaseOrder.length - 1) {
    return phaseOrder[currentIndex + 1];
  }
  return 'COMPLETE';
}

export interface BurstPacketResult {
  packet: SyncPacket | null;
  session: RadioBurstSession;
  complete: boolean;
}

export async function runBurstStep(
  session: RadioBurstSession,
  localNode: SyncNode,
  localEntities: Map<UUID, Entity>,
  localDeltas: Map<UUID, Delta[]>,
  entityTypes: Map<UUID, EntityType>,
  peerPacket: SyncPacket | null
): Promise<BurstPacketResult> {
  let packet: SyncPacket | null = null;
  let updatedSession = { ...session };

  switch (session.phase) {
    case 'IDLE':
      // Start with HELLO
      packet = createHelloPacket(localNode);
      updatedSession.phase = 'HELLO';
      updatedSession.packets_sent++;
      break;

    case 'HELLO':
      // After HELLO exchange, send HEADS
      if (peerPacket?.type === 'HELLO') {
        updatedSession.peer_node_id = peerPacket.node_id;
        packet = createHeadsPacket(
          localNode.node_id,
          Array.from(localEntities.entries()).map(([id, entity]) => ({
            entity,
            entityType: entityTypes.get(id) || 'note',
          }))
        );
        updatedSession.phase = 'HEADS';
        updatedSession.packets_sent++;
        updatedSession.packets_received++;
      }
      break;

    case 'HEADS':
      // After HEADS exchange, compute WANTs
      if (peerPacket?.type === 'HEADS') {
        const localHeads = Array.from(localEntities.entries()).map(([id, entity]) => ({
          entity_id: id,
          entity_type: entityTypes.get(id) || ('note' as EntityType),
          current_hash: entity.current_hash,
          current_version: entity.current_version,
        }));

        const diff = computeHeadsDiff(localHeads, peerPacket.heads);
        const wants = generateWantEntries(diff, localDeltas);

        if (wants.length > 0) {
          packet = createWantPacket(localNode.node_id, wants);
          updatedSession.phase = 'WANT';
        } else {
          // Nothing to want, go to ACK
          packet = createAckPacket(localNode.node_id, []);
          updatedSession.phase = 'ACK';
        }
        updatedSession.packets_sent++;
        updatedSession.packets_received++;
      }
      break;

    case 'WANT':
      // After WANT, expect DELTAS
      if (peerPacket?.type === 'DELTAS') {
        // Receive deltas, send ACK
        const deltaIds = peerPacket.deltas.map((d) => d.delta_id);
        packet = createAckPacket(localNode.node_id, deltaIds);
        updatedSession.phase = 'ACK';
        updatedSession.packets_sent++;
        updatedSession.packets_received++;
      } else if (peerPacket?.type === 'WANT') {
        // Peer wants from us, send DELTAS
        const deltasToSend: Delta[] = [];
        for (const want of peerPacket.wants) {
          const entityDeltas = localDeltas.get(want.entity_id) || [];
          // Find deltas after since_hash
          let found = want.since_hash === '0'.repeat(64);
          for (const delta of entityDeltas) {
            if (found) deltasToSend.push(delta);
            if (delta.new_hash === want.since_hash) found = true;
          }
        }

        const prioritized = prioritizeDeltas(deltasToSend, entityTypes);
        packet = createDeltasPacket(
          localNode.node_id,
          prioritized.map((p) => p.delta)
        );
        updatedSession.phase = 'DELTAS';
        updatedSession.packets_sent++;
        updatedSession.packets_received++;
      }
      break;

    case 'DELTAS':
      // After sending DELTAS, expect ACK
      if (peerPacket?.type === 'ACK') {
        updatedSession.phase = 'COMPLETE';
        updatedSession.packets_received++;
      }
      break;

    case 'ACK':
      // After ACK, complete
      updatedSession.phase = 'COMPLETE';
      break;

    case 'COMPLETE':
    case 'ERROR':
      // Terminal states
      break;
  }

  // Track bytes
  if (packet) {
    updatedSession.bytes_transmitted += JSON.stringify(packet).length;
  }

  return {
    packet,
    session: updatedSession,
    complete: updatedSession.phase === 'COMPLETE' || updatedSession.phase === 'ERROR',
  };
}

// === MICRO NODE MINIMAL SHELL ===

export interface MicroShellState {
  message_count: number;
  task_count: number;
  pending_count: number;
  last_sync_at: Timestamp | null;
  display_lines: string[]; // 4 lines for LCD
}

export function createMicroShellState(
  messages: number,
  tasks: number,
  pending: number,
  lastSync: Timestamp | null
): MicroShellState {
  const lines = [
    `M:${messages} T:${tasks} P:${pending}`,
    lastSync ? `Sync: ${formatTimestamp(lastSync)}` : 'No sync',
    pending > 0 ? 'ACTION PENDING' : 'Ready',
    '---',
  ];

  return {
    message_count: messages,
    task_count: tasks,
    pending_count: pending,
    last_sync_at: lastSync,
    display_lines: lines,
  };
}

function formatTimestamp(ts: Timestamp): string {
  const date = new Date(ts);
  return `${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}`;
}

export function renderMicroShell(state: MicroShellState): string {
  return state.display_lines.join('\n');
}

// === NODE LIFECYCLE ===

export interface NodeLifecycle {
  boot: () => void;
  tick: (deltaMs: number) => void;
  onRadioReceive: (packet: SyncPacket) => void;
  onUserInput: (input: ShellInput) => void;
  shutdown: () => void;
}

export function createNodeLifecycle(
  config: NodeRuntimeConfig,
  syncNode: SyncNode,
  onStateChange: (config: NodeRuntimeConfig) => void
): NodeLifecycle {
  let runtime = config;
  let burstSession: RadioBurstSession | null = null;

  return {
    boot: () => {
      runtime = wakeNode(runtime, 'user');
      onStateChange(runtime);
    },

    tick: (deltaMs: number) => {
      runtime = {
        ...runtime,
        uptime_ms: runtime.uptime_ms + deltaMs,
      };

      // Check power state transitions
      runtime = updatePowerState(runtime, now());

      // Check if should wake from timer
      if (shouldWake(runtime, now())) {
        runtime = wakeNode(runtime, 'timer');
      }

      onStateChange(runtime);
    },

    onRadioReceive: (packet: SyncPacket) => {
      // Wake on radio if sleeping
      if (runtime.wake_on_radio && runtime.power_state === 'DEEP_SLEEP') {
        runtime = wakeNode(runtime, 'radio');
      }

      // Start burst session if needed
      if (!burstSession || burstSession.phase === 'COMPLETE') {
        burstSession = createRadioBurstSession(syncNode.node_id);
      }

      runtime.last_activity_at = now();
      onStateChange(runtime);
    },

    onUserInput: (input: ShellInput) => {
      runtime = wakeNode(runtime, 'user');
      onStateChange(runtime);
    },

    shutdown: () => {
      runtime = enterDeepSleep(runtime);
      onStateChange(runtime);
    },
  };
}

// === ENTITY FILTERING FOR NODE CLASS ===

export function filterEntitiesForNodeClass(
  nodeClass: NodeClass,
  entities: Array<{ entity: Entity; entityType: EntityType }>
): Array<{ entity: Entity; entityType: EntityType }> {
  const supported = SUPPORTED_ENTITY_TYPES[nodeClass];
  return entities.filter((e) => supported.includes(e.entityType));
}

export function filterDeltasForNodeClass(
  nodeClass: NodeClass,
  deltas: Delta[],
  entityTypes: Map<UUID, EntityType>
): Delta[] {
  const supported = SUPPORTED_ENTITY_TYPES[nodeClass];
  return deltas.filter((d) => {
    const entityType = entityTypes.get(d.entity_id);
    return entityType && supported.includes(entityType);
  });
}
