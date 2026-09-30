"use client";

import React from "react";
import { History, Clock, Activity } from "lucide-react";

export interface AuditLogEntry {
  id: string;
  claim_id: string;
  stage_name: string;
  input_summary: string;
  output_summary: string;
  execution_time_ms: number;
  timestamp: string;
}

interface AuditTrailViewerProps {
  entries: AuditLogEntry[];
}

export const AuditTrailViewer: React.FC<AuditTrailViewerProps> = ({ entries }) => {
  if (!entries || entries.length === 0) return null;

  return (
    <div
      className="card shadow-sm"
      style={{ border: "1px solid #e5e7eb", borderRadius: 14, backgroundColor: "#ffffff" }}
    >
      <div className="card-body" style={{ padding: "20px 24px 24px" }}>
        {/* Header */}
        <div
          className="d-flex align-items-center gap-3 pb-3 mb-3"
          style={{ borderBottom: "1px solid #f1f5f9" }}
        >
          <div
            className="d-flex align-items-center justify-content-center rounded"
            style={{ width: 38, height: 38, backgroundColor: "#e7f0ff" }}
          >
            <History size={17} color="#0d6efd" />
          </div>
          <div>
            <h3 className="mb-0 fw-bold" style={{ fontSize: "1rem", color: "#0f172a" }}>
              Verification Audit Trail
            </h3>
            <p className="mb-0" style={{ fontSize: "0.76rem", color: "#64748b" }}>
              Step-by-step immutable execution logs and timing metrics
            </p>
          </div>
        </div>

        {/* Timeline */}
        <div style={{ position: "relative", paddingLeft: 24 }}>
          {/* Vertical line */}
          <div
            style={{
              position: "absolute",
              left: 8,
              top: 8,
              bottom: 8,
              width: 2,
              backgroundColor: "#e5e7eb",
            }}
          />

          <div className="d-flex flex-column gap-3">
            {entries.map((entry, index) => (
              <div key={entry.id || index} style={{ position: "relative" }}>
                {/* Dot */}
                <div
                  style={{
                    position: "absolute",
                    left: -20,
                    top: 14,
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    backgroundColor: "#0d6efd",
                    border: "2px solid #ffffff",
                    boxShadow: "0 0 0 2px #0d6efd",
                  }}
                />

                <div
                  className="p-3 rounded"
                  style={{ backgroundColor: "#f8f9fa", border: "1px solid #e5e7eb" }}
                >
                  <div className="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
                    <div className="d-flex align-items-center gap-2">
                      <Activity size={14} color="#0d6efd" />
                      <span
                        className="fw-bold text-uppercase"
                        style={{ fontSize: "0.75rem", color: "#0f172a", letterSpacing: "0.06em" }}
                      >
                        {entry.stage_name}
                      </span>
                    </div>
                    <div className="d-flex align-items-center gap-3" style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                      <div className="d-flex align-items-center gap-1">
                        <Clock size={11} />
                        <span>{entry.execution_time_ms} ms</span>
                      </div>
                      <span>{new Date(entry.timestamp).toLocaleTimeString()}</span>
                    </div>
                  </div>

                  <div className="row g-2" style={{ fontSize: "0.78rem" }}>
                    <div className="col-12 col-md-6">
                      <p
                        className="mb-1 fw-semibold text-uppercase"
                        style={{ fontSize: "0.65rem", color: "#94a3b8", letterSpacing: "0.06em" }}
                      >
                        Stage Input
                      </p>
                      <p className="mb-0" style={{ color: "#334155", fontFamily: "monospace" }}>
                        {entry.input_summary}
                      </p>
                    </div>
                    <div className="col-12 col-md-6">
                      <p
                        className="mb-1 fw-semibold text-uppercase"
                        style={{ fontSize: "0.65rem", color: "#94a3b8", letterSpacing: "0.06em" }}
                      >
                        Stage Output
                      </p>
                      <p className="mb-0" style={{ color: "#334155", fontFamily: "monospace" }}>
                        {entry.output_summary}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
