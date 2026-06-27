import { getAccessToken } from "./supabase";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

/** Thin fetch wrapper: prefixes the API base, JSON in/out, optional bearer auth.
 *  Throws `Error("Not signed in")` when `auth` is set but no token, and
 *  `Error("API <status>")` on a non-2xx response. */
async function request<T>(
  path: string,
  opts: { method?: string; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  const { method = "GET", body, auth = false } = opts;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    const token = await getAccessToken();
    if (!token) throw new Error("Not signed in");
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return (await res.json()) as T;
}

// --- /chat (authed) --------------------------------------------------------- #
export type Turn = { role: "user" | "assistant"; content: string };

export async function sendChat(message: string, history: Turn[]): Promise<string> {
  const data = await request<{ reply: string }>("/chat", {
    method: "POST",
    body: { message, history },
    auth: true,
  });
  return data.reply;
}

// --- Citator types — mirror app/src/htl/models/api.py exactly ---------------- #
export type ResolveResult = {
  found: boolean;
  case_id: number | null;
  case_name: string | null;
  citation: string | null;
  court: string | null;
  date_filed: string | null;
  source: string | null;
  ambiguous: boolean;
};

export type CaseRef = {
  case_id: number;
  case_name: string | null;
  citation: string | null;
  court: string | null;
  date_filed: string | null;
};

export type TrendPoint = { year: number; neg: number; pos: number; neg_share: number };

export type CitingCaseRef = {
  case_name: string | null;
  court: string | null;
  date_filed: string | null;
};

export type Treatment = {
  citing_case: CitingCaseRef;
  type: string;
  scope: string | null;
  on_other_grounds: boolean;
  quote: string | null;
  confidence: number | null;
};

export type PositiveSignal = { approving_cites: number; total_citing: number };

export type GroundTruth = { on_loc_overruled_list: boolean; overruled_by: string | null };

export type RiskResult = {
  case: CaseRef;
  as_of: string;
  signal: string;
  status: string;
  risk_score: number;
  risk_rationale: string;
  trend: TrendPoint[];
  negative_treatments: Treatment[];
  positive_signal: PositiveSignal;
  ground_truth: GroundTruth;
};

// --- Citator calls (public, no auth) ---------------------------------------- #
export async function resolve(query: string): Promise<ResolveResult> {
  return request("/resolve", { method: "POST", body: { query } });
}

export async function caseRisk(id: number): Promise<RiskResult> {
  return request(`/cases/${id}/risk`);
}
