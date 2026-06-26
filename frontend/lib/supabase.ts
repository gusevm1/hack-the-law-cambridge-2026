import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Lazy singleton so a build without Supabase env doesn't crash at import time —
// it only errors when a chat is actually sent without auth configured.
let _client: SupabaseClient | null = null;

function client(): SupabaseClient {
  if (!_client) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!url || !key) throw new Error("Supabase env not configured");
    _client = createClient(url, key);
  }
  return _client;
}

/** Current access token, signing in anonymously on first use. */
export async function getAccessToken(): Promise<string> {
  const c = client();
  const { data } = await c.auth.getSession();
  if (data.session?.access_token) return data.session.access_token;

  const { data: signedIn, error } = await c.auth.signInAnonymously();
  if (error || !signedIn.session) {
    throw new Error(error?.message ?? "anonymous sign-in failed");
  }
  return signedIn.session.access_token;
}
