"use client";

import { AttributionResult } from "../../lib/api";

export default function OriginTracker({ data }: { data: AttributionResult }) {
  if (!data) return null;

  return (
    <div style={{
      background: "var(--bg-base)",
      border: "1px solid var(--border)",
      borderRadius: "var(--radius-xl)",
      padding: "24px",
      boxShadow: "var(--shadow-sm)",
      marginBottom: "24px"
    }}>
      <h3 style={{
        margin: "0 0 16px",
        fontSize: "1.1rem",
        fontWeight: 700,
        color: "var(--text-primary)",
        display: "flex",
        alignItems: "center",
        gap: "8px"
      }}>
        🕵️ Traceability & Attribution
      </h3>

      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        
        {/* Generative Source Badge */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: "12px", borderBottom: "1px solid var(--border)" }}>
          <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: 600 }}>Generative Source</span>
          <span style={{
            fontSize: "0.85rem",
            fontWeight: 700,
            color: data.resemble_source.includes("Organic") ? "var(--emerald-500)" : "var(--indigo-600)",
            background: data.resemble_source.includes("Organic") ? "var(--emerald-50)" : "var(--indigo-50)",
            padding: "4px 10px",
            borderRadius: "999px",
            border: `1px solid ${data.resemble_source.includes("Organic") ? "var(--emerald-100)" : "var(--indigo-100)"}`
          }}>
            {data.resemble_source || "Unknown"}
          </span>
        </div>

        {/* Patient Zero Timeline */}
        <div style={{ paddingBottom: "12px", borderBottom: "1px solid var(--border)" }}>
          <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: 600, display: "block", marginBottom: "8px" }}>
            Temporal OSINT (Patient Zero)
          </span>
          {data.patient_zero_date ? (
            <div style={{ fontSize: "0.85rem", color: "var(--text-primary)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
                <span style={{ color: "var(--rose-500)" }}>📅</span> 
                <strong>Earliest upload:</strong> {data.patient_zero_date}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <span style={{ color: "var(--amber-500)" }}>🔗</span>
                <a href={data.patient_zero_url!} target="_blank" rel="noreferrer" style={{ color: "var(--indigo-500)", textDecoration: "none", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "250px", display: "inline-block", verticalAlign: "bottom" }}>
                  {data.patient_zero_url}
                </a>
              </div>
            </div>
          ) : (
            <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", fontStyle: "italic" }}>
              No historical matches found prior to current viral spread.
            </div>
          )}
        </div>

        {/* Culprit Intel */}
        <div>
          <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: 600, display: "block", marginBottom: "8px" }}>
            Extracted Culprit Intel
          </span>
          {data.culprit_handles && data.culprit_handles.length > 0 ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
              {data.culprit_handles.map((handle, idx) => (
                <span key={idx} style={{
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: "var(--rose-500)",
                  background: "var(--rose-50)",
                  padding: "4px 8px",
                  borderRadius: "6px",
                  border: "1px solid var(--rose-100)"
                }}>
                  {handle}
                </span>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", fontStyle: "italic" }}>
              No identifiable handles extracted from Patient Zero.
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
