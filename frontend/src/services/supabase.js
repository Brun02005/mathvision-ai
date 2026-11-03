/**
 * Supabase Auth client. Without VITE_SUPABASE_URL (local development) accounts are
 * off: the backend then runs everything as a single local user, and so does the UI.
 *
 * The publishable ("anon") key is meant to be public: it identifies the project, it
 * does not grant access by itself. Never put the service_role key in the frontend.
 */
import { createClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const authEnabled = Boolean(url && key);
export const supabase = authEnabled ? createClient(url, key) : null;

/** Current access token (refreshed by the SDK when it is about to expire), or null. */
export async function accessToken() {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
