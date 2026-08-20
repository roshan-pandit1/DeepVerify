"use client";

import { CheckCircle2, XCircle, AlertTriangle, Info } from "lucide-react";
import type { VerdictResult, VisionResult } from "../../lib/api";

interface FindingsPanelProps {
  verdict: VerdictResult;
  vision: VisionResult;
}

export function FindingsPanel({ verdict, vision }: FindingsPanelProps) {
  const { key_findings, confidence_breakdown, c2pa_status } = verdict;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Key Findings */}
      <div className="card" style={{ padding: "24px" }}>
        <h2 style={{ margin: "0 0 16px", fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
          🔎 Key Forensic Findings
        </h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {key_findings.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
              No key findings were generated.
            </p>
          ) : (
            key_findings.map((finding, i) => (
              <div
                key={i}
                className="animate-fade-in-up"
                style={{
                  display: "flex", gap: "12px", alignItems: "flex-start",
                  padding: "12px 14px", borderRadius: "var(--radius-md)",
                  background: "var(--bg-surface)", border: "1px solid var(--border)",
                  animationDelay: `${i * 0.08}s`,
                }}
              >
                <CheckCircle2 size={16} color="var(--indigo-600)" style={{ flexShrink: 0, marginTop: "2px" }} />
                <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                  {finding}
                </p>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Confidence Breakdown */}
      {confidence_breakdown && Object.keys(confidence_breakdown).length > 0 && (
        <div className="card" style={{ padding: "24px" }}>
          <h2 style={{ margin: "0 0 16px", fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
            📊 Evidence Weight Breakdown
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {Object.entries(confidence_breakdown).map(([key, value]) => {
              const label = key
                .replace(/_weight$/, "")
                .replace(/_/g, " ")
                .replace(/\b\w/g, (c) => c.toUpperCase());
              const pct = Math.min(100, Math.max(0, Number(value)));
              return (
                <div key={key}>
                  <div style={{
                    display: "flex", justifyContent: "space-between",
                    marginBottom: "6px",
                  }}>
                    <span style={{ fontSize: "0.82rem", fontWeight: 500, color: "var(--text-secondary)" }}>
                      {label}
                    </span>
                    <span style={{
                      fontSize: "0.8rem", fontWeight: 700,
                      fontFamily: "JetBrains Mono, monospace",
                      color: pct > 60 ? "var(--rose-500)" : pct > 30 ? "var(--amber-500)" : "var(--emerald-500)",
                    }}>
                      {pct}
                    </span>
                  </div>
                  <div className="progress-track">
                    <div
                      className="progress-fill"
                      style={{
                        width: `${pct}%`,
                        background: pct > 60
                          ? "linear-gradient(90deg, #f43f5e, #fb7185)"
                          : pct > 30
                          ? "linear-gradient(90deg, #f59e0b, #fbbf24)"
                          : "linear-gradient(90deg, #10b981, #34d399)",
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* C2PA Detail */}
      <div className="card" style={{ padding: "24px" }}>
        <h2 style={{ margin: "0 0 16px", fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
          🔐 C2PA Content Credentials
        </h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {[
            {
              label: "Status",
              value: c2pa_status?.status ?? "unknown",
              highlight: c2pa_status?.is_ai_generated,
            },
            {
              label: "AI Generated",
              value: c2pa_status?.is_ai_generated ? "Yes ⚠️" : "No ✓",
              highlight: c2pa_status?.is_ai_generated,
            },
            {
              label: "Generator",
              value: c2pa_status?.generator ?? "N/A",
              highlight: false,
            },
            {
              label: "Digital Source Type",
              value: c2pa_status?.digital_source_type ?? "N/A",
              highlight: false,
            },
            {
              label: "Issuer",
              value: c2pa_status?.issuer ?? "N/A",
              highlight: false,
            },
          ].map(({ label, value, highlight }) => (
            <div
              key={label}
              style={{
                display: "flex", justifyContent: "space-between", alignItems: "flex-start",
                padding: "8px 12px", borderRadius: "var(--radius-sm)",
                background: "var(--bg-surface)", gap: "12px",
              }}
            >
              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 500, flexShrink: 0 }}>
                {label}
              </span>
              <span style={{
                fontSize: "0.82rem", fontWeight: 600,
                color: highlight ? "var(--rose-500)" : "var(--text-secondary)",
                textAlign: "right", wordBreak: "break-all",
                fontFamily: value?.startsWith("http") ? "JetBrains Mono, monospace" : "inherit",
              }}>
                {String(value)}
              </span>
            </div>
          ))}

          {/* Full message */}
          <div style={{
            padding: "10px 12px", borderRadius: "var(--radius-sm)",
            background: "var(--bg-subtle)", border: "1px solid var(--border)",
            display: "flex", gap: "8px", alignItems: "flex-start",
          }}>
            <Info size={14} color="var(--text-muted)" style={{ flexShrink: 0, marginTop: "2px" }} />
            <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-muted)", lineHeight: 1.5 }}>
              {c2pa_status?.message ?? "No C2PA information available."}
            </p>
          </div>
        </div>
      </div>

      {/* Vision Stats */}
      <div className="card" style={{ padding: "24px" }}>
        <h2 style={{ margin: "0 0 16px", fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
          👁️ Vision Analysis Summary
        </h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px" }}>
          {[
            { label: "Facial Artifact Score", value: `${vision.facial_artifact_score.toFixed(1)}%`, danger: vision.facial_artifact_score > 60 },
            { label: "Faces Detected", value: String(vision.faces_detected), danger: false },
            { label: "Frames Analyzed", value: String(vision.frames_analyzed), danger: false },
            { label: "Suspicious Frames", value: String(vision.suspicious_frames.length), danger: vision.suspicious_frames.length > 0 },
          ].map(({ label, value, danger }) => (
            <div
              key={label}
              style={{
                padding: "14px 12px", borderRadius: "var(--radius-md)",
                background: danger ? "var(--rose-50)" : "var(--bg-surface)",
                border: `1px solid ${danger ? "var(--rose-100)" : "var(--border)"}`,
                textAlign: "center",
              }}
            >
              <p style={{
                margin: "0 0 4px", fontSize: "1.4rem", fontWeight: 800,
                color: danger ? "var(--rose-500)" : "var(--text-primary)",
                fontFamily: "JetBrains Mono, monospace",
              }}>
                {value}
              </p>
              <p style={{ margin: 0, fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 500 }}>
                {label}
              </p>
            </div>
          ))}
        </div>
        {vision.skipped_reason && (
          <p style={{
            marginTop: "12px", fontSize: "0.8rem", color: "var(--text-muted)",
            padding: "8px 12px", background: "var(--bg-subtle)", borderRadius: "var(--radius-sm)",
          }}>
            ⚠️ {vision.skipped_reason}
          </p>
        )}
      </div>
    </div>
  );
}
