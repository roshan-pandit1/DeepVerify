"use client";

import { useRef } from "react";
import type { AudioResult } from "../../lib/api";

interface TranscriptViewerProps {
  audio: AudioResult;
  onSeek?: (time: number) => void;
}

export function TranscriptViewer({ audio, onSeek }: TranscriptViewerProps) {
  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  if (audio.skipped) {
    return (
      <div className="card" style={{ padding: "28px" }}>
        <h2 style={{ margin: "0 0 8px", fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
          🎙️ Audio Transcript
        </h2>
        <div style={{
          padding: "16px", borderRadius: "var(--radius-md)",
          background: "var(--bg-subtle)", border: "1px solid var(--border)",
          color: "var(--text-muted)", fontSize: "0.875rem",
        }}>
          <span>⚠️</span>{" "}
          {audio.skip_reason || "No audio track found in this video."}
        </div>
      </div>
    );
  }

  return (
    <div className="card" style={{ overflow: "hidden" }}>
      <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 700, color: "var(--text-primary)" }}>
              🎙️ Audio Transcript
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: "0.8rem", color: "var(--text-muted)" }}>
              Groq Whisper large-v3 · Language: <strong>{audio.language}</strong> · {audio.duration.toFixed(1)}s
            </p>
          </div>
          {onSeek && (
            <span style={{ fontSize: "0.75rem", color: "var(--indigo-600)", fontWeight: 500 }}>
              Click timestamp to jump
            </span>
          )}
        </div>
      </div>

      {/* Full text summary */}
      {audio.full_text && (
        <div style={{
          margin: "16px 24px 0",
          padding: "14px 16px",
          background: "var(--indigo-50)",
          border: "1px solid var(--indigo-100)",
          borderRadius: "var(--radius-md)",
          fontSize: "0.875rem",
          color: "var(--text-secondary)",
          lineHeight: 1.6,
          fontStyle: "italic",
        }}>
          "{audio.full_text.slice(0, 400)}{audio.full_text.length > 400 ? "…" : ""}"
        </div>
      )}

      {/* Segments */}
      <div style={{
        maxHeight: "340px", overflowY: "auto",
        padding: "12px 24px 20px",
        display: "flex", flexDirection: "column", gap: "4px",
      }}>
        {audio.segments.length === 0 ? (
          <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", padding: "8px 0" }}>
            No timestamped segments available.
          </p>
        ) : (
          audio.segments.map((seg, i) => (
            <div
              key={i}
              style={{
                display: "flex", gap: "12px", alignItems: "flex-start",
                padding: "8px 10px", borderRadius: "var(--radius-sm)",
                transition: "background 0.1s ease", cursor: onSeek ? "pointer" : "default",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-subtle)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              onClick={() => onSeek?.(seg.start)}
            >
              <span style={{
                flexShrink: 0, fontFamily: "JetBrains Mono, monospace",
                fontSize: "0.72rem", color: "var(--indigo-600)",
                background: "var(--indigo-50)", padding: "2px 7px",
                borderRadius: "4px", marginTop: "2px", fontWeight: 500,
              }}>
                {formatTime(seg.start)}
              </span>
              <span style={{ fontSize: "0.875rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                {seg.text}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
