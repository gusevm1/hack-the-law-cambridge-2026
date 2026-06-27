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

// --- /cases/{id}/graph — the treatment network (public) --------------------- #
// Mirrors app/src/htl/models/api.py GraphNode/GraphEdge/GraphResponse.
export type GraphNode = {
  case_id: number;
  case_name: string | null;
  citation: string | null;
  court: string | null;
  date_filed: string | null;
  is_focal: boolean;
};

export type GraphEdge = {
  citing_id: number;
  cited_id: number;
  treatment: string | null;
  polarity: "negative" | "positive" | "neutral";
  confidence: number | null;
  quote: string | null;
  on_other_grounds: boolean;
  source_url: string | null;
};

export type GraphResult = {
  focal: CaseRef;
  signal: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export async function caseGraph(id: number): Promise<GraphResult> {
  return request(`/cases/${id}/graph`);
}

// --- /cases/{id}/inspect — raw DB dump for the dev inspector ----------------- #
export type InspectTreatment = {
  type: string | null;
  scope: string | null;
  on_other_grounds: boolean;
  confidence: number | null;
  model: string | null;
  quote: string | null;
};
export type InspectEdge = {
  citing_id: number;
  case_name: string | null;
  court: string | null;
  tier: string;
  date_filed: string | null;
  citation: string | null;
  source: string | null;
  depth: number | null;
  has_passage: boolean;
  passage_chars: number;
  passage_preview: string | null;
  treatments: InspectTreatment[];
  opinion_url: string | null;
};
export type InspectResult = {
  target: {
    case_id: number;
    case_name: string | null;
    court: string | null;
    date_filed: string | null;
    citation: string | null;
    source: string | null;
    in_db: boolean;
  };
  counts: {
    edges: number;
    classified: number;
    unclassified: number;
    with_passage: number;
    binding: number;
  };
  edges: InspectEdge[];
};

export async function caseInspect(id: number): Promise<InspectResult> {
  return request(`/cases/${id}/inspect`);
}

// --- /ask — agentic citator assistant (public) ------------------------------ #
// Mirrors app/src/htl/models/api.py AskRequest/AskResponse.
export type AskResult = {
  answer: string;
  resolved_case: ResolveResult | null;
  verdict: RiskResult | null;
};

// `caseText` avoids the JS reserved word; the request body key is `case`.
export async function ask(caseText: string, use: string): Promise<AskResult> {
  return request("/ask", { method: "POST", body: { case: caseText, use } });
}
