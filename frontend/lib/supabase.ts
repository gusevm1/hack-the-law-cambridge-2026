import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Lazy browser-client singleton. persistSession / autoRefreshToken /
// detectSessionInUrl default to true, so the session survives reloads and the
// OAuth redirect (?code=…) is exchanged automatically on load.
let _client: SupabaseClient | null = null;

/** Browser client, or null when Supabase env isn't configured (e.g. local
 *  citator-only dev). Lets public pages render without auth instead of the
 *  whole app white-screening. */
export function supabaseOrNull(): SupabaseClient | null {
  if (!_client) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!url || !key) return null;
    _client = createClient(url, key);
  }
  return _client;
}

export function supabase(): SupabaseClient {
  const client = supabaseOrNull();
  if (!client) throw new Error("Supabase env not configured");
  return client;
}

/** Current access token, or null when signed out / auth unconfigured. */
export async function getAccessToken(): Promise<string | null> {
  const client = supabaseOrNull();
  if (!client) return null;
  const { data } = await client.auth.getSession();
  return data.session?.access_token ?? null;
}
