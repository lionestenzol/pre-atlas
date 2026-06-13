// Delta SCP · Supabase client factory

import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { loadConfig, requireSupabase, type ScpConfig } from './config.js';

let cached: SupabaseClient | null = null;

/** Returns a singleton service-role Supabase client. */
export function getSupabase(config: ScpConfig = loadConfig()): SupabaseClient {
  if (cached) return cached;
  requireSupabase(config);
  cached = createClient(config.supabaseUrl, config.supabaseServiceKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return cached;
}
