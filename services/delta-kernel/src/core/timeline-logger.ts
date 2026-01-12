/**
 * Timeline Logger — Phase 6C Event Logging
 *
 * Append-only event log for temporal visibility.
 * Every significant state change writes an event here.
 */

import * as fs from 'fs';
import * as path from 'path';

// === TYPES ===

export type TimelineEventType =
  | 'WORK_REQUESTED'
  | 'WORK_APPROVED'
  | 'WORK_DENIED'
  | 'WORK_QUEUED'
  | 'WORK_COMPLETED'
  | 'WORK_FAILED'
  | 'WORK_ABANDONED'
  | 'WORK_TIMEOUT'
  | 'WORK_CANCELLED'
  | 'LOOP_OPENED'
  | 'LOOP_CLOSED'
  | 'MODE_CHANGED'
  | 'STREAK_UPDATED'
  | 'DAEMON_HEARTBEAT'
  | 'SYSTEM_START';

export type TimelineSource =
  | 'work_controller'
  | 'governance_daemon'
  | 'api'
  | 'cli'
  | 'system';

export interface TimelineEvent {
  id: string;
  ts: string;
  type: TimelineEventType;
  source: TimelineSource;
  data?: Record<string, unknown>;
}

export interface TimelineLog {
  events: TimelineEvent[];
  meta: {
    version: string;
    created_at: string;
    last_event_at: string | null;
    event_count: number;
  };
}

// === LOGGER CLASS ===

export class TimelineLogger {
  private filePath: string;
  private log: TimelineLog;
  private maxEvents: number;

  constructor(repoRoot: string, maxEvents: number = 10000) {
    this.filePath = path.join(repoRoot, 'services', 'cognitive-sensor', 'timeline_events.json');
    this.maxEvents = maxEvents;
    this.log = this.loadOrCreate();
  }

  /**
   * Load existing log or create new one.
   */
  private loadOrCreate(): TimelineLog {
    try {
      if (fs.existsSync(this.filePath)) {
        const content = fs.readFileSync(this.filePath, 'utf-8');
        return JSON.parse(content) as TimelineLog;
      }
    } catch (error) {
      console.error('[TimelineLogger] Error loading log, creating new:', error);
    }

    // Create new log
    const newLog: TimelineLog = {
      events: [],
      meta: {
        version: '1.0',
        created_at: new Date().toISOString(),
        last_event_at: null,
        event_count: 0,
      },
    };

    this.save(newLog);
    return newLog;
  }

  /**
   * Save log to disk.
   */
  private save(log: TimelineLog): void {
    try {
      const dir = path.dirname(this.filePath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      fs.writeFileSync(this.filePath, JSON.stringify(log, null, 2), 'utf-8');
    } catch (error) {
      console.error('[TimelineLogger] Error saving log:', error);
    }
  }

  /**
   * Generate unique event ID.
   */
  private generateId(): string {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let id = 'e_';
    for (let i = 0; i < 16; i++) {
      id += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return id;
  }

  /**
   * Emit an event to the timeline.
   */
  emit(type: TimelineEventType, source: TimelineSource, data?: Record<string, unknown>): TimelineEvent {
    const event: TimelineEvent = {
      id: this.generateId(),
      ts: new Date().toISOString(),
      type,
      source,
      data,
    };

    // Add to log
    this.log.events.push(event);
    this.log.meta.last_event_at = event.ts;
    this.log.meta.event_count = this.log.events.length;

    // Trim if over max (keep most recent)
    if (this.log.events.length > this.maxEvents) {
      this.log.events = this.log.events.slice(-this.maxEvents);
    }

    // Persist
    this.save(this.log);

    return event;
  }

  /**
   * Query events by time range.
   */
  query(options: {
    from?: string;
    to?: string;
    type?: TimelineEventType;
    source?: TimelineSource;
    limit?: number;
  } = {}): TimelineEvent[] {
    let results = [...this.log.events];

    // Filter by time range
    if (options.from) {
      const fromTime = new Date(options.from).getTime();
      results = results.filter(e => new Date(e.ts).getTime() >= fromTime);
    }
    if (options.to) {
      const toTime = new Date(options.to).getTime();
      results = results.filter(e => new Date(e.ts).getTime() <= toTime);
    }

    // Filter by type
    if (options.type) {
      results = results.filter(e => e.type === options.type);
    }

    // Filter by source
    if (options.source) {
      results = results.filter(e => e.source === options.source);
    }

    // Sort by time (newest first for queries)
    results.sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime());

    // Apply limit
    if (options.limit && options.limit > 0) {
      results = results.slice(0, options.limit);
    }

    return results;
  }

  /**
   * Get events for a specific day.
   */
  getDay(date: string): TimelineEvent[] {
    const dayStart = new Date(date);
    dayStart.setHours(0, 0, 0, 0);
    const dayEnd = new Date(date);
    dayEnd.setHours(23, 59, 59, 999);

    return this.query({
      from: dayStart.toISOString(),
      to: dayEnd.toISOString(),
    });
  }

  /**
   * Get summary stats.
   */
  getStats(): {
    total: number;
    by_type: Record<string, number>;
    by_source: Record<string, number>;
    first_event: string | null;
    last_event: string | null;
  } {
    const byType: Record<string, number> = {};
    const bySource: Record<string, number> = {};

    for (const event of this.log.events) {
      byType[event.type] = (byType[event.type] || 0) + 1;
      bySource[event.source] = (bySource[event.source] || 0) + 1;
    }

    return {
      total: this.log.meta.event_count,
      by_type: byType,
      by_source: bySource,
      first_event: this.log.events.length > 0 ? this.log.events[0].ts : null,
      last_event: this.log.meta.last_event_at,
    };
  }

  /**
   * Get raw log (for debugging).
   */
  getLog(): TimelineLog {
    return this.log;
  }
}

// === SINGLETON ===

let loggerInstance: TimelineLogger | null = null;

export function getTimelineLogger(repoRoot: string): TimelineLogger {
  if (!loggerInstance) {
    loggerInstance = new TimelineLogger(repoRoot);
  }
  return loggerInstance;
}
