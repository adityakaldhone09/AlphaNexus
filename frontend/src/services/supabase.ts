/**
 * AlphaNexus — Centralized Supabase Client
 * ========================================
 * Singleton client for optional Supabase Auth and Storage integration.
 * All primary financial intelligence queries route through FastAPI.
 */

import { createClient, SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://ceedxgiuppobapaypxnb.supabase.co';
const supabasePublishableKey =
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ||
  import.meta.env.VITE_SUPABASE_ANON_KEY ||
  '';

let _supabaseClient: SupabaseClient | null = null;

export const getSupabaseClient = (): SupabaseClient | null => {
  if (_supabaseClient) {
    return _supabaseClient;
  }

  if (!supabaseUrl || !supabasePublishableKey) {
    // Return null in development when publishable key is not set; avoids crashes
    return null;
  }

  try {
    _supabaseClient = createClient(supabaseUrl, supabasePublishableKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
    return _supabaseClient;
  } catch (err) {
    console.warn('[Supabase] Client initialization failed:', err);
    return null;
  }
};

/**
 * Direct exported singleton instance (null-safe wrapper).
 */
export const supabase = getSupabaseClient();

/**
 * Helper to test Supabase client availability in the frontend.
 */
export const isSupabaseConfigured = (): boolean => {
  return Boolean(supabaseUrl && supabasePublishableKey);
};

