/**
 * Aegis Enterprise Fabric — Entity Registry
 *
 * Maps entity types to their data interfaces and provides
 * type-safe entity creation helpers.
 */

import { AegisEntityType } from './types.js';

export const ENTITY_TYPES: readonly AegisEntityType[] = [
  'aegis_tenant',
  'aegis_agent',
  'aegis_task',
  'aegis_policy',
  'aegis_approval',
  'aegis_webhook',
  'aegis_usage_record',
  'aegis_audit_entry',
] as const;

export function isValidEntityType(type: string): type is AegisEntityType {
  return ENTITY_TYPES.includes(type as AegisEntityType);
}
