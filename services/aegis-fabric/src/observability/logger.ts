/**
 * Aegis Enterprise Fabric — Structured Logger
 *
 * JSON-formatted structured logging to stdout.
 */

import { UUID } from '../core/types.js';

export type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

const LEVEL_ORDER: Record<LogLevel, number> = {
  DEBUG: 0, INFO: 1, WARN: 2, ERROR: 3,
};

let currentLevel: LogLevel = 'INFO';

export function setLogLevel(level: LogLevel): void {
  currentLevel = level;
}

export function log(
  level: LogLevel,
  message: string,
  data?: Record<string, unknown>
): void {
  if (LEVEL_ORDER[level] < LEVEL_ORDER[currentLevel]) return;

  const entry = {
    level,
    timestamp: new Date().toISOString(),
    service: 'aegis-fabric',
    message,
    ...data,
  };

  if (level === 'ERROR') {
    console.error(JSON.stringify(entry));
  } else {
    console.log(JSON.stringify(entry));
  }
}

export const logger = {
  debug: (msg: string, data?: Record<string, unknown>) => log('DEBUG', msg, data),
  info: (msg: string, data?: Record<string, unknown>) => log('INFO', msg, data),
  warn: (msg: string, data?: Record<string, unknown>) => log('WARN', msg, data),
  error: (msg: string, data?: Record<string, unknown>) => log('ERROR', msg, data),
};
