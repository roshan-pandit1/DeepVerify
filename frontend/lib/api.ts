/**
 * lib/api.ts — Typed API client for the Video Authenticity Engine backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────

export interface AnalyzeResponse {
  job_id: string;
}

export interface StatusResponse {
  job_id: string;
  status:
    | "pending"
    | "ingesting"
    | "c2pa"
    | "audio"
    | "vision"
    | "osint"
    | "synthesis"
    | "complete"
    | "failed";
  stage_label: string;
  stage_step: number;
  total_steps: number;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface TimelineEvent {
  type: "vision" | "audio";
  timestamp: number;
  label: string;
  score: number | null;
  is_anomaly: boolean;
  frame_url: string | null;
  gradcam_url: string | null;
}

export interface VerdictResult {
  authenticity_score: number;
  verdict_category:
    | "Authentic"
    | "AI-Generated Deepfake"
    | "Out-of-Context Cheapfake"
    | "Manipulated Audio"
    | "Inconclusive";
  summary_headline: string;
  key_findings: string[];
  confidence_breakdown: Record<string, number>;
  c2pa_status: {
    status: string;
    is_ai_generated: boolean;
    digital_source_type: string | null;
    issuer: string | null;
    generator: string | null;
    message: string;
  };
  timeline_events: TimelineEvent[];
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface AudioResult {
  full_text: string;
  language: string;
  duration: number;
  skipped: boolean;
  skip_reason: string;
  segments: TranscriptSegment[];
}

export interface OsintMatch {
  title: string;
  url: string;
  source: string;
  thumbnail: string | null;
  date_published: string | null;
}

export interface OsintResult {
  matches: OsintMatch[];
  keyframes_searched: number;
  skipped: boolean;
  skip_reason: string;
}

export interface FrameScore {
  frame_path: string;
  timestamp: number;
  face_detected: boolean;
  manipulation_score: number;
  gradcam_path: string | null;
}

export interface VisionResult {
  facial_artifact_score: number;
  faces_detected: number;
  frames_analyzed: number;
  skipped_reason: string | null;
  error: string | null;
  frame_scores: FrameScore[];
  suspicious_frames: FrameScore[];
}

export interface VideoMeta {
  duration_seconds: number;
  fps: number;
  width: number;
  height: number;
  video_path: string;
  keyframe_paths: string[];
}

export interface AttributionResult {
  resemble_source: string;
  patient_zero_date: string | null;
  patient_zero_url: string | null;
  culprit_handles: string[];
}

export interface BlockchainResult {
  /** "sealed" = on-chain confirmed, "off_chain" = no keys set, "pending" = tx broadcast but not confirmed */
  status: "sealed" | "off_chain" | "pending";
  /** Hex SHA-256 of the raw video file bytes */
  sha256?: string | null;
  /** Perceptual hash fingerprint (imagehash pHash) */
  phash?: string | null;
  /** IPFS CID of the pinned forensic report JSON */
  ipfs_cid?: string | null;
  /** On-chain transaction hash (0x-prefixed) */
  tx_hash?: string | null;
  /** ISO-8601 timestamp of when the tx was confirmed */
  timestamp?: string | null;
}

export interface ReportResponse {
  job_id: string;
  verdict: VerdictResult;
  audio: AudioResult;
  vision: VisionResult;
  osint: OsintResult;
  attribution: AttributionResult;
  video_meta: VideoMeta;
  /** Blockchain provenance metadata — absent on jobs run before this feature was added */
  blockchain?: BlockchainResult;
}

// ── API Functions ──────────────────────────────────────────────────────────

/** Submit a video file for analysis. */
export async function analyzeFile(file: File): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/analyze`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err?.detail ?? "Upload failed");
  }
  return res.json();
}

/** Submit a social media URL for analysis. */
export async function analyzeUrl(url: string): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("source_url", url);
  const res = await fetch(`${API_BASE}/api/analyze`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err?.detail ?? "Analysis request failed");
  }
  return res.json();
}

/** Poll job status. */
export async function getStatus(jobId: string): Promise<StatusResponse> {
  const res = await fetch(`${API_BASE}/api/status/${jobId}`);
  if (!res.ok) throw new Error(`Status fetch failed: ${res.status}`);
  return res.json();
}

/** Fetch full forensic report. */
export async function getReport(jobId: string): Promise<ReportResponse> {
  const res = await fetch(`${API_BASE}/api/report/${jobId}`);
  if (res.status === 202) {
    const body = await res.json();
    throw new Error(`Analysis in progress: ${body?.detail?.status ?? "pending"}`);
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err?.detail?.message ?? err?.detail ?? "Report fetch failed");
  }
  return res.json();
}

/** Helper: build a public URL from a static path served by FastAPI */
export function staticUrl(path: string | null): string | null {
  if (!path) return null;
  // path is like /tmp/uploads/.../gradcam_...png
  // FastAPI serves /tmp at /static/
  const rel = path.replace(/^\/tmp\//, "");
  return `${API_BASE}/static/${rel}`;
}

export interface JobListItem {
  job_id: string;
  status: string;
  source_type: string;
  original_filename: string | null;
  created_at: string | null;
}

/** Fetch recent jobs. */
export async function getJobs(limit = 20): Promise<JobListItem[]> {
  const res = await fetch(`${API_BASE}/api/jobs?limit=${limit}`);
  if (!res.ok) throw new Error(`Jobs fetch failed: ${res.status}`);
  return res.json();
}
