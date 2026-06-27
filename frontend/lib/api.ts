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

// --- Citations + triage (citator filter stage) — mirror api.py exactly ------ #
export type Edge = {
  citing_case: CitingCaseRef;
  citation: string | null;
  passage: string;
  source: string; // "graph" | "fulltext"
  matched_citation: string | null;
  opinion_url: string | null;
};

export type CitationsResult = { case: CaseRef; total: number; edges: Edge[] };

export type TriageSignals = {
  binding: boolean;
  treatment_kw: string[];
  propositions_engaged: string[];
  recency_years: number;
};

export type TieredEdge = Edge & {
  tier: string; // "deep" | "shallow" | "mention"
  reasons: string[];
  signals: TriageSignals;
};

export type TriageCounts = { deep: number; shallow: number; mention: number };

export type TriageResult = {
  case: CaseRef;
  total: number;
  counts: TriageCounts;
  edges: TieredEdge[];
};

export async function caseCitations(id: number): Promise<CitationsResult> {
  return request(`/cases/${id}/citations`);
}

export async function caseTriage(id: number): Promise<TriageResult> {
  return request(`/cases/${id}/triage`);
}

export type EdgeClassification = {
  treatment: string;
  proposition: string | null;
  holding_vs_dicta: string;
  attribution: string; // "self" | "reported"
  quote: string;
  confidence: number;
  model: string;
};

export type ClassifiedEdge = TieredEdge & { classification: EdgeClassification | null };

export type ClassifyResult = {
  case: CaseRef;
  total: number;
  counts: TriageCounts;
  classified: number;
  edges: ClassifiedEdge[];
};

export async function caseClassify(id: number): Promise<ClassifyResult> {
  return request(`/cases/${id}/classify`);
}

// ============================================================================ //
// Pipeline contracts — Features 3–5. Mirror app/src/htl/models/api.py exactly.
// Defined up front so the parallel features build to identical shapes; each
// feature adds its own fetch function. See citator-pipeline-contracts.md.
// ============================================================================ //

// --- Feature 3 (A): /cases/{id}/analyze ------------------------------------- #
export type PropositionFinding = {
  proposition: string | null;
  treatment: string;
  what_changed: string;
  holding_vs_dicta: string;
  attribution: string; // "self" | "reported"
  quote: string;
  confidence: number;
};

export type AnalyzedEdge = TieredEdge & {
  analysis_depth: string; // "full-text" | "snippet"
  findings: PropositionFinding[];
  case_summary: string;
  model: string;
};

export type AnalyzeResult = {
  case: CaseRef;
  total: number;
  counts: TriageCounts;
  analyzed: number;
  edges: AnalyzedEdge[];
};

// --- Feature 4 (B): /cases/{id}/propositions -------------------------------- #
export type TimelinePoint = {
  year: number;
  court: string | null;
  case_name: string | null;
  treatment: string;
  polarity: number; // -1 | 0 | +1
};

export type CircuitSplit = {
  present: boolean;
  follows: string[];
  limits: string[];
  summary: string;
};

export type CertStatus = {
  granted: boolean;
  case_name: string | null;
  term: string | null;
  question: string | null;
  source: string | null;
  as_of: string | null;
};

export type CloseToOverruled = { flag: boolean; confidence: number; rationale: string };

export type PropositionVerdict = {
  proposition_id: string;
  label: string;
  summary: string;
  signal: string; // "green" | "amber" | "red" | "unknown"
  status: string;
  risk_score: number;
  what_changed: string;
  timeline: TimelinePoint[];
  circuit_split: CircuitSplit | null;
  cert: CertStatus | null;
  close_to_overruled: CloseToOverruled;
  supporting_edges: string[];
};

export type PropositionsResult = {
  case: CaseRef;
  operative_rule: string;
  propositions: PropositionVerdict[];
  as_of: string;
};

// --- Feature 5 (C): POST /cases/{id}/verdict -------------------------------- #
export type UseMapping = {
  use_label: string;
  intent: string;
  engaged_propositions: string[];
  rationale: string;
};

export type UseProposition = {
  proposition_id: string;
  signal: string;
  relevant_to_use: boolean;
  note: string;
};

export type VerdictResult = {
  case: CaseRef;
  operative_rule: string;
  use: UseMapping;
  real_risk: boolean;
  risk_explanation: string;
  per_proposition: UseProposition[];
  final_labels: string[];
  close_to_overruled: CloseToOverruled;
  as_of: string;
};

export async function caseVerdict(
  id: number,
  use: string,
  intent: string,
): Promise<VerdictResult> {
  return request(`/cases/${id}/verdict`, { method: "POST", body: { use, intent } });
}
