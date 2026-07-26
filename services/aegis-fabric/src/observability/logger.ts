/**
 * Aegis Enterprise Fabric — Structured logger (pino-backed).
 *
 * Public API preserved: logger.<level>(msg, data?) so existing callsites in
 * src/api/** do not move. See ~/.claude/rules/common/assemble-first.md.
 */

import pino from 'pino';

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const pinoLogger = pino({
  level: (process.env.LOG_LEVEL?.toLowerCase() as LogLevel) ?? 'info',
  base: { service: 'aegis-fabric' },
});

export function setLogLevel(level: LogLevel): void {
  pinoLogger.level = level;
}

export const logger = {
  debug: (msg: string, data?: Record<string, unknown>) => pinoLogger.debug(data ?? {}, msg),
  info:  (msg: string, data?: Record<string, unknown>) => pinoLogger.info(data ?? {}, msg),
  warn:  (msg: string, data?: Record<string, unknown>) => pinoLogger.warn(data ?? {}, msg),
  error: (msg: string, data?: Record<string, unknown>) => pinoLogger.error(data ?? {}, msg),
};
