"use client";

import React from "react";
import { CheckCircle2, Tag, FileText, Calendar } from "lucide-react";

interface Assertion {
  id: string;
  assertion_text: string;
  entities: string[];
  confidence_weight: number;
}

interface ClaimDetailViewProps {
  claim: {
    id: string;
    raw_input: string;
    normalized_text?: string;
    status: string;
    created_at: string;
    assertions?: Assertion[];
  };
}

export const ClaimDetailView: React.FC<ClaimDetailViewProps> = ({ claim }) => {
  const isComplete = claim.status === "completed";

  return (
    <div
      className="card shadow-sm"
      style={{ border: "1px solid #e5e7eb", borderRadius: 14, backgroundColor: "#ffffff" }}
    >
      <div className="card-body" style={{ padding: "20px 24px 24px" }}>
        {/* Header */}
        <div
          className="d-flex flex-wrap align-items-center justify-content-between gap-3 pb-3 mb-3"
          style={{ borderBottom: "1px solid #f1f5f9" }}
        >
          <div className="d-flex align-items-center gap-3">
            <div
              className="d-flex align-items-center justify-content-center rounded"
              style={{ width: 38, height: 38, backgroundColor: "#e7f0ff" }}
            >
              <FileText size={17} color="#0d6efd" />
            </div>
            <div>
              <h3 className="mb-0 fw-semibold" style={{ fontSize: "1rem", color: "#0f172a" }}>
                Claim Investigation #{claim.id.slice(0, 8)}
              </h3>
              <div className="d-flex align-items-center gap-1 mt-1" style={{ color: "#94a3b8", fontSize: "0.75rem" }}>
                <Calendar size={12} />
                <span>{new Date(claim.created_at).toLocaleString()}</span>
              </div>
            </div>
          </div>
          <span
            className={`badge rounded-pill ${isComplete ? "text-bg-success" : "text-bg-warning"}`}
            style={{ fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}
          >
            {claim.status}
          </span>
        </div>

        {/* Original submission */}
        <div className="mb-3">
          <p
            className="mb-1 fw-semibold text-uppercase"
            style={{ fontSize: "0.7rem", color: "#94a3b8", letterSpacing: "0.06em" }}
          >
            Original Submission
          </p>
          <div
            className="p-3 rounded"
            style={{ backgroundColor: "#f8f9fa", border: "1px solid #e5e7eb", fontSize: "0.875rem", color: "#334155", fontFamily: "monospace", lineHeight: 1.6 }}
          >
            {claim.raw_input}
          </div>
        </div>

        {/* Normalized text */}
        {claim.normalized_text && (
          <div className="mb-3">
            <p
              className="mb-1 fw-semibold text-uppercase"
              style={{ fontSize: "0.7rem", color: "#94a3b8", letterSpacing: "0.06em" }}
            >
              Normalized Claim Unit
            </p>
            <div
              className="p-3 rounded"
              style={{ backgroundColor: "#f8f9fa", border: "1px solid #e5e7eb", fontSize: "0.875rem", color: "#334155", lineHeight: 1.6 }}
            >
              {claim.normalized_text}
            </div>
          </div>
        )}

        {/* Assertions */}
        {claim.assertions && claim.assertions.length > 0 && (
          <div>
            <p
              className="mb-2 fw-semibold text-uppercase"
              style={{ fontSize: "0.7rem", color: "#94a3b8", letterSpacing: "0.06em" }}
            >
              Extracted Sub-Assertions &amp; Entities
            </p>
            <div className="d-flex flex-column gap-2">
              {claim.assertions.map((a, i) => (
                <div
                  key={a.id || i}
                  className="p-3 rounded"
                  style={{ backgroundColor: "#f8f9fa", border: "1px solid #e5e7eb" }}
                >
                  <div className="d-flex align-items-start gap-2 mb-2">
                    <CheckCircle2 size={15} color="#0d6efd" style={{ marginTop: 2, flexShrink: 0 }} />
                    <span style={{ fontSize: "0.875rem", color: "#0f172a", fontWeight: 500 }}>{a.assertion_text}</span>
                  </div>
                  {a.entities && a.entities.length > 0 && (
                    <div className="d-flex flex-wrap align-items-center gap-1" style={{ paddingLeft: 23 }}>
                      <Tag size={12} color="#94a3b8" />
                      {a.entities.map((e, idx) => (
                        <span
                          key={idx}
                          className="badge"
                          style={{ backgroundColor: "#e7f0ff", color: "#0d6efd", fontWeight: 500, fontSize: "0.7rem" }}
                        >
                          {e}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
