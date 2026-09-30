"use client";

import React from "react";
import { ShieldCheck, AlertTriangle, XCircle, HelpCircle, ExternalLink, Award } from "lucide-react";

export interface EvidenceItem {
  id: string;
  source_name: string;
  source_url?: string;
  content_snippet: string;
  stance: "supports" | "refutes" | "neutral";
  credibility_score: number;
}

export interface VerdictReport {
  id: string;
  claim_id: string;
  verdict: "Verified" | "Uncertain" | "Unsupported" | "Contested";
  confidence_score: number;
  summary_explanation: string;
  evidence_items: EvidenceItem[];
  completed_at: string;
}

interface VerdictCardProps {
  report: VerdictReport;
}

const verdictConfig = {
  Verified: {
    icon: <ShieldCheck size={22} color="#198754" />,
    alertClass: "alert-success",
    barColor: "#198754",
    badgeClass: "text-bg-success",
  },
  Unsupported: {
    icon: <XCircle size={22} color="#dc3545" />,
    alertClass: "alert-danger",
    barColor: "#dc3545",
    badgeClass: "text-bg-danger",
  },
  Contested: {
    icon: <AlertTriangle size={22} color="#ffc107" />,
    alertClass: "alert-warning",
    barColor: "#ffc107",
    badgeClass: "text-bg-warning",
  },
  Uncertain: {
    icon: <HelpCircle size={22} color="#0d6efd" />,
    alertClass: "alert-primary",
    barColor: "#0d6efd",
    badgeClass: "text-bg-primary",
  },
};

const stanceBadge = (stance: string) => {
  if (stance === "supports") return { bg: "#d1fae5", color: "#065f46", label: "Supports" };
  if (stance === "refutes") return { bg: "#fee2e2", color: "#991b1b", label: "Refutes" };
  return { bg: "#f1f5f9", color: "#475569", label: "Neutral" };
};

export const VerdictCard: React.FC<VerdictCardProps> = ({ report }) => {
  const cfg = verdictConfig[report.verdict] ?? verdictConfig.Uncertain;

  return (
    <div className="d-flex flex-column gap-3">
      {/* Verdict Summary */}
      <div
        className={`alert ${cfg.alertClass} shadow-sm`}
        role="alert"
        style={{ borderRadius: 14, border: "1px solid", padding: "1.25rem" }}
      >
        <div className="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-3">
          <div className="d-flex align-items-center gap-3">
            <div
              className="d-flex align-items-center justify-content-center rounded"
              style={{ width: 42, height: 42, backgroundColor: "rgba(255,255,255,0.7)", border: "1px solid rgba(0,0,0,0.08)" }}
            >
              {cfg.icon}
            </div>
            <div>
              <p className="mb-0" style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", opacity: 0.7 }}>
                Verification Classification
              </p>
              <h3 className="mb-0 fw-black" style={{ fontSize: "1.4rem" }}>
                {report.verdict}
              </h3>
            </div>
          </div>
          <div className="text-end">
            <p className="mb-0" style={{ fontSize: "0.68rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", opacity: 0.7 }}>
              Confidence Index
            </p>
            <div className="fw-black" style={{ fontSize: "1.5rem" }}>{report.confidence_score}%</div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="progress mb-3" style={{ height: 8, borderRadius: 99, backgroundColor: "rgba(255,255,255,0.5)" }}>
          <div
            className="progress-bar"
            role="progressbar"
            style={{ width: `${report.confidence_score}%`, backgroundColor: cfg.barColor, borderRadius: 99, transition: "width 0.7s ease" }}
          />
        </div>

        <p style={{ fontSize: "0.875rem", marginBottom: 0, lineHeight: 1.65 }}>
          {report.summary_explanation}
        </p>
      </div>

      {/* Evidence sources */}
      {report.evidence_items && report.evidence_items.length > 0 && (
        <div
          className="card shadow-sm"
          style={{ border: "1px solid #e5e7eb", borderRadius: 14, backgroundColor: "#ffffff" }}
        >
          <div className="card-body" style={{ padding: "20px 24px 24px" }}>
            <h4
              className="d-flex align-items-center gap-2 mb-3 fw-semibold"
              style={{ fontSize: "0.82rem", textTransform: "uppercase", letterSpacing: "0.06em", color: "#64748b" }}
            >
              <Award size={15} color="#0d6efd" />
              Corroborating OSINT &amp; Source Evidence ({report.evidence_items.length})
            </h4>

            <div className="row g-3">
              {report.evidence_items.map((ev) => {
                const sb = stanceBadge(ev.stance);
                return (
                  <div key={ev.id} className="col-12 col-md-6">
                    <div
                      className="h-100 p-3 rounded d-flex flex-column justify-content-between gap-2"
                      style={{ backgroundColor: "#f8f9fa", border: "1px solid #e5e7eb" }}
                    >
                      <div>
                        <div className="d-flex align-items-center justify-content-between mb-2">
                          <span className="fw-bold" style={{ fontSize: "0.75rem", color: "#0d6efd", textTransform: "uppercase" }}>
                            {ev.source_name}
                          </span>
                          <span
                            className="badge"
                            style={{ backgroundColor: sb.bg, color: sb.color, fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase" }}
                          >
                            {sb.label}
                          </span>
                        </div>
                        <p className="mb-0 fst-italic" style={{ fontSize: "0.8rem", color: "#475569", lineHeight: 1.55, display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                          &ldquo;{ev.content_snippet}&rdquo;
                        </p>
                      </div>
                      <div
                        className="d-flex align-items-center justify-content-between pt-2"
                        style={{ borderTop: "1px solid #e5e7eb", fontSize: "0.75rem", color: "#94a3b8" }}
                      >
                        <span>
                          Credibility:{" "}
                          <strong style={{ color: "#0f172a" }}>{(ev.credibility_score * 100).toFixed(0)}%</strong>
                        </span>
                        {ev.source_url && (
                          <a
                            href={ev.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn btn-outline-primary btn-sm py-0 d-flex align-items-center gap-1"
                            style={{ fontSize: "0.72rem" }}
                          >
                            Source <ExternalLink size={11} />
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
