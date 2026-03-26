export type Mode = 'RECOVER' | 'CLOSURE' | 'MAINTENANCE' | 'BUILD' | 'COMPOUND' | 'SCALE';

// Panel 1: AI Usage Counter
export interface UsageData {
  ai_seconds_used: number;
  free_tier_seconds: number;
  paused: boolean;
}

// Panel 2: Atlas Clusters
export interface IdeaItem {
  canonical_id: string;
  canonical_title: string;
  priority_score: number;
  priority_breakdown: {
    frequency: number;
    recency: number;
    alignment: number;
    feasibility: number;
    compounding: number;
  };
  category: string;
  status: string;
  complexity: string;
  mention_count: number;
  alignment_score: number;
  dependencies: string[];
  child_ideas: string[];
}

export interface IdeaRegistryData {
  metadata: {
    generated_at: string;
    total_ideas: number;
    reference_date: string;
    tier_breakdown: Record<string, number>;
    max_priority: number;
    avg_priority: number;
  };
  tiers: Record<string, IdeaItem[]>;
}

// Panel 3: Simulation
export interface SimulationSummary {
  simulation_id: string;
  status: string;
  topic: string;
  agent_count: number;
  tick_count: number;
}

export interface SimulationTick {
  tick_number: number;
  consensus: number;
  agents: Array<{ id: string; position: number; confidence: number }>;
}

export interface SimulationDetail extends SimulationSummary {
  ticks: SimulationTick[];
}

export interface SimulationReport {
  simulation_id: string;
  topic: string;
  summary: string;
  consensus_reached: boolean;
  final_consensus: number;
}

// Panel 4: Festival Manager
export interface OrchestratorStatus {
  timestamp: string;
  mode: Mode;
  risk: string;
  build_allowed: boolean;
  open_loops: number;
  festival: Record<string, unknown>;
}

// Panel 5: Mode & Governance
export interface UnifiedDerived {
  mode: Mode;
  risk: string;
  open_loops: number;
  closure_ratio: number;
  primary_order: string;
  build_allowed: boolean;
  enforcement_level: number;
  violations_count: number;
  overrides_count: number;
  override_available: boolean;
  closures_today: number;
  total_closures: number;
  streak_days: number;
  best_streak: number;
}

export interface UnifiedState {
  ok: boolean;
  ts: string;
  delta: Record<string, unknown>;
  cognitive: Record<string, unknown>;
  derived: UnifiedDerived;
  errors: string[];
}
