"use client";

import { useState } from "react";
import type { TimelineEvent } from "../../lib/api";

interface HeatmapViewerProps {
  suspiciousFrames: Array<{
    timestamp: number;
    manipulation_score: number;
    gradcam_path: string | null;
    frame_path: string;
  }>;
  timelineEvents: TimelineEvent[];
}

export function HeatmapViewer({ suspiciousFrames, timelineEvents }: HeatmapViewerProps) {
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [showHeatmap, setShowHeatmap] = useState(false);

  // Merge: prefer suspiciousFrames with gradcam, fall back to timeline events
  const framesWithHeatmap = [
    ...suspiciousFrames.filter((f) => f.gradcam_path),
    ...timelineEvents
      .filter((e) => e.is_anomaly && e.gradcam_url && e.frame_url)
      .map((e) => ({
        timestamp: e.timestamp,
        manipulation_score: (e.score ?? 0) / 100,
        gradcam_path: e.gradcam_url!,
        frame_path: e.frame_url!,
      })),
  ].slice(0, 6); // Show at most 6

  if (framesWithHeatmap.length === 0) {
    return (
      <div className="card" style={{ padding: "28px" }}>
        <h2 style={{ margin: "0 0 8px", fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
          🔥 Facial Artifact Heatmap
        </h2>
        <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", margin: 0 }}>
          No faces detected in this video, or no frames exceeded the 60% manipulation threshold.
          Grad-CAM heatmaps are generated only for high-confidence suspicious frames.
        </p>
      </div>
    );
  }

  const current = framesWithHeatmap[selectedIdx];
  const displayUrl = showHeatmap
    ? (current.gradcam_path ?? current.frame_path)
    : current.frame_path;

  return (
    <div className="card" style={{ overflow: "hidden" }}>
      <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
            🔥 Facial Artifact Heatmap
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Grad-CAM activation overlay — red = model attention to manipulation artifacts
          </p>
        </div>

        {/* Toggle */}
        <div className="heatmap-toggle" style={{ width: "200px" }}>
          <button
            className={`heatmap-toggle-btn${!showHeatmap ? " active" : ""}`}
            onClick={() => setShowHeatmap(false)}
          >
            Raw Frame
          </button>
          <button
            className={`heatmap-toggle-btn${showHeatmap ? " active" : ""}`}
            onClick={() => setShowHeatmap(true)}
          >
            Heatmap
          </button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 0 }}>
        {/* Main image */}
        <div style={{ flex: 1, position: "relative", background: "#000", minHeight: "280px" }}>
          {displayUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={displayUrl}
              alt={showHeatmap ? "Grad-CAM heatmap" : "Video frame"}
              style={{ width: "100%", height: "100%", objectFit: "contain", display: "block", maxHeight: "360px" }}
              crossOrigin="anonymous"
            />
          ) : (
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              height: "280px", color: "#666", fontSize: "0.875rem",
            }}>
              Frame not available
            </div>
          )}

          {/* Score overlay */}
          <div style={{
            position: "absolute", top: "12px", right: "12px",
            padding: "6px 12px", borderRadius: "999px",
            background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)",
            color: "#fff", fontSize: "0.8rem", fontWeight: 700,
            fontFamily: "JetBrains Mono, monospace",
          }}>
            {(current.manipulation_score * 100).toFixed(1)}% suspicious
          </div>

          {/* Timestamp overlay */}
          <div style={{
            position: "absolute", bottom: "12px", left: "12px",
            padding: "4px 10px", borderRadius: "999px",
            background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)",
            color: "#cbd5e1", fontSize: "0.75rem", fontWeight: 500,
            fontFamily: "JetBrains Mono, monospace",
          }}>
            t={current.timestamp.toFixed(2)}s
          </div>
        </div>

        {/* Thumbnail strip */}
        {framesWithHeatmap.length > 1 && (
          <div style={{
            width: "100px", display: "flex", flexDirection: "column", gap: "2px",
            background: "var(--bg-surface)", borderLeft: "1px solid var(--border)",
            padding: "8px", overflowY: "auto",
          }}>
            {framesWithHeatmap.map((f, i) => (
              <button
                key={i}
                onClick={() => setSelectedIdx(i)}
                style={{
                  border: i === selectedIdx ? "2px solid var(--indigo-500)" : "2px solid transparent",
                  borderRadius: "var(--radius-sm)", overflow: "hidden",
                  cursor: "pointer", padding: 0, background: "transparent", position: "relative",
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={showHeatmap ? (f.gradcam_path ?? f.frame_path) : f.frame_path}
                  alt={`Frame ${i}`}
                  style={{ width: "100%", height: "60px", objectFit: "cover", display: "block" }}
                  crossOrigin="anonymous"
                />
                <div style={{
                  position: "absolute", bottom: 0, left: 0, right: 0,
                  background: "rgba(0,0,0,0.6)", color: "#fff", fontSize: "0.6rem",
                  padding: "2px 4px", fontFamily: "JetBrains Mono, monospace",
                  textAlign: "center",
                }}>
                  {(f.manipulation_score * 100).toFixed(0)}%
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
