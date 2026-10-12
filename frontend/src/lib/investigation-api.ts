export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(/\/$/, "");

export async function api<T>(path: string, method = "GET", body?: unknown, token?: string): Promise<T> {
  const response = await fetch(`${API_BASE}/api${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || response.statusText);
    throw new Error(detail);
  }
  return response.json();
}

export type Feedback = { id: string; dimension: string; label: string; approval: string };
export type Evidence = {
  id: string; source_name: string; source_url: string; content_snippet: string;
  publication_date: string | null; retrieved_at: string; retrieval_method: string;
  passage_kind: string; predicted_stance: string; effective_stance: string;
  classification_method: string; explanation: string; fixture: number; ranker: string; feedback: Feedback[];
  source: {
    source_id: string; final_url: string; source_retrieved_at: string; extraction_method: string;
    extraction_status: string; extraction_error: string | null; content_hash: string | null;
    body_hash: string | null; date_method: string | null; context: string; search_snippet: string;
    start_offset: number | null; end_offset: number | null; selection_method: string;
  } | null;
};
export type Assertion = {
  id: string; assertion_text: string; entity_names_json: string; dates: string; locations: string;
  assessment: string; explanation: string; evidence: Evidence[];
};
export type Summary = { claim_id: string; stage: string; provider: string; memory_text: string; created_at: string };
export type Investigation = Summary & {
  error: string | null; assertions: Assertion[];
  job: { state: string; attempts: number } | null;
  searches: { id: string; assertion_id: string; query: string; provider: string; retrieved_at: string; state: string; error: string | null }[];
  audit: { id: string; stage_name: string; output_summary: string; timestamp: string }[];
  related: (Summary & { method: string; reuse: string })[];
};
export type Learning = { status: string; active_ranker: string; effective_ranker: string; approved_live_examples: number; memory: string; training: string };
