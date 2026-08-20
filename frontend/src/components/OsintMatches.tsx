"use client";

import { ExternalLink, Search } from "lucide-react";
import type { OsintResult } from "../../lib/api";

interface OsintMatchesProps {
  osint: OsintResult;
}

export function OsintMatches({ osint }: OsintMatchesProps) {
  if (osint.skipped) {
    return (
      <div className="card" style={{ padding: "28px" }}>
        <h2 style={{ margin: "0 0 8px", fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
          🔍 Reverse Image OSINT
        </h2>
        <div style={{
          padding: "16px", borderRadius: "var(--radius-md)",
          background: "var(--bg-subtle)", border: "1px solid var(--border)",
          color: "var(--text-muted)", fontSize: "0.875rem",
        }}>
          ⚠️ {osint.skip_reason || "Reverse image search was not performed."}
        </div>
      </div>
    );
  }

  return (
    <div className="card" style={{ overflow: "hidden" }}>
      <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border)" }}>
        <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
          🔍 Reverse Image OSINT
        </h2>
        <p style={{ margin: "4px 0 0", fontSize: "0.8rem", color: "var(--text-muted)" }}>
          Google Lens searched {osint.keyframes_searched} scene keyframes · {osint.matches.length} web matches found
        </p>
      </div>

      <div style={{ padding: "16px 24px", display: "flex", flexDirection: "column", gap: "10px" }}>
        {osint.matches.length === 0 ? (
          <div style={{
            padding: "20px", textAlign: "center",
            background: "var(--bg-subtle)", borderRadius: "var(--radius-md)",
          }}>
            <Search size={24} color="var(--text-muted)" style={{ marginBottom: "8px" }} />
            <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", margin: 0 }}>
              No matching web sources found for the scene keyframes.
              This could indicate original footage or very recent content.
            </p>
          </div>
        ) : (
          osint.matches.map((match, i) => (
            <a
              key={i}
              href={match.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "flex", gap: "14px", alignItems: "flex-start",
                padding: "14px 16px", borderRadius: "var(--radius-md)",
                border: "1px solid var(--border)", background: "var(--bg-base)",
                textDecoration: "none", transition: "all 0.15s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--bg-subtle)";
                e.currentTarget.style.borderColor = "var(--indigo-500)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "var(--bg-base)";
                e.currentTarget.style.borderColor = "var(--border)";
              }}
            >
              {/* Thumbnail */}
              {match.thumbnail ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={match.thumbnail}
                  alt=""
                  style={{
                    width: "64px", height: "48px", objectFit: "cover",
                    borderRadius: "var(--radius-sm)", flexShrink: 0, background: "var(--bg-muted)",
                  }}
                />
              ) : (
                <div style={{
                  width: "64px", height: "48px", background: "var(--bg-muted)",
                  borderRadius: "var(--radius-sm)", flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <Search size={18} color="var(--text-muted)" />
                </div>
              )}

              {/* Info */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{
                  margin: 0, fontWeight: 600, fontSize: "0.875rem",
                  color: "var(--text-primary)",
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}>
                  {match.title || "(No title)"}
                </p>
                <p style={{
                  margin: "4px 0 0", fontSize: "0.78rem", color: "var(--text-muted)",
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}>
                  {match.source || match.url}
                </p>
                {match.date_published && (
                  <span style={{
                    display: "inline-block", marginTop: "6px",
                    padding: "2px 8px", borderRadius: "999px",
                    background: "var(--amber-50)", border: "1px solid var(--amber-100)",
                    fontSize: "0.72rem", color: "#92400e", fontWeight: 600,
                  }}>
                    📅 Published: {match.date_published}
                  </span>
                )}
              </div>

              <ExternalLink size={14} color="var(--text-muted)" style={{ flexShrink: 0, marginTop: "4px" }} />
            </a>
          ))
        )}
      </div>
    </div>
  );
}
