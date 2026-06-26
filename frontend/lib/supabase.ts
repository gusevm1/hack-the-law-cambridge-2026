import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Lazy browser-client singleton. persistSession / autoRefreshToken /
// detectSessionInUrl default to true, so the session survives reloads and the
// OAuth redirect (?code=…) is exchanged automatically on load.
let _client: SupabaseClient | null = null;

export function supabase(): SupabaseClient {
  if (!_client) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!url || !key) throw new Error("Supabase env not configured");
    _client = createClient(url, key);
  }
  return _client;
}

/** Current access token, or null when signed out. */
export async function getAccessToken(): Promise<string | null> {
  const { data } = await supabase().auth.getSession();
  return data.session?.access_token ?? null;
}
