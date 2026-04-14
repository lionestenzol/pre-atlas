/**
 * Aegis Enterprise Fabric — Request Logger
 *
 * Structured JSONL request/response logging.
 */

import * as path from 'path';
import { UUID, Timestamp } from '../core/types.js';
import { AegisStorage } from '../storage/aegis-storage.js';

export interface RequestLogEntry {
  timestamp: Timestamp;
  tenant_id: UUID | null;
  agent_id: UUID | null;
  method: string;
  path: string;
  status_code: number;
  duration_ms: number;
  request_id: string;
}

export class RequestLogger {
  private storage: AegisStorage;
  private logFile: string;

  constructor(storage: AegisStorage) {
    this.storage = storage;
    this.logFile = path.join(storage.getDataDir(), 'request-log.jsonl');
  }

  log(entry: RequestLogEntry): void {
    this.storage.appendJsonl(this.logFile, entry);
  }

  getRecentLogs(limit: number = 100): RequestLogEntry[] {
    const all = this.storage.readJsonl<RequestLogEntry>(this.logFile);
    return all.slice(-limit);
  }
}
