"use client";

import { Shield, ShieldAlert, ShieldOff, ShieldCheck, HelpCircle } from "lucide-react";
import type { VerdictResult } from "../../lib/api";

interface ReportHeaderProps {
  verdict: VerdictResult;
  jobId: string;
}

type VerdictCategory = VerdictResult["verdict_category"];

const VERDICT_CONFIG: Record<VerdictCategory, {
  label: string;
  bg: string;
  border: string;
  text: string;
  ringColor: string;
  glow: string;
  icon: React.ReactNode;
  badgeClass: string;
}> = {
  "Authentic": {
    label: "Authentic",
    bg: "var(--emerald-50)",
    border: "var(--emerald-100)",
    text: "#065f46",
    ringColor: "#10b981",
    glow: "rgba(16,185,129,0.15)",
    icon: <ShieldCheck size={28} />,
    badgeClass: "badge-authentic",
  },
  "AI-Generated Deepfake": {
    label: "AI Deepfake",
    bg: "var(--rose-50)",
    border: "var(--rose-100)",
    text: "#9f1239",
    ringColor: "#f43f5e",
    glow: "rgba(244,63,94,0.15)",
    icon: <ShieldAlert size={28} />,
    badgeClass: "badge-deepfake",
  },
  "Out-of-Context Cheapfake": {
    label: "Cheapfake",
    bg: "var(--amber-50)",
    border: "var(--amber-100)",
    text: "#92400e",
    ringColor: "#f59e0b",
    glow: "rgba(245,158,11,0.15)",
    icon: <ShieldOff size={28} />,
    badgeClass: "badge-cheapfake",
  },
  "Manipulated Audio": {
    label: "Audio Manipulation",
    bg: "var(--violet-50)",
    border: "var(--violet-100)",
    text: "#0369a1",
    ringColor: "#0ea5e9",
    glow: "rgba(14,165,233,0.15)",
    icon: <ShieldAlert size={28} />,
    badgeClass: "badge-audio",
  },
  "Inconclusive": {
    label: "Inconclusive",
    bg: "var(--bg-subtle)",
    border: "var(--border)",
    text: "var(--text-secondary)",
    ringColor: "#94a3b8",
    glow: "rgba(148,163,184,0.1)",
    icon: <HelpCircle size={28} />,
    badgeClass: "badge-inconclusive",
  },
};

function ScoreRing({ score, color, glow }: { score: number; color: string; glow: string }) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const filled = (score / 100) * circumference;

  return (
    <div style={{ position: "relative", width: "140px", height: "140px" }}>
      {/* Glow */}
      <div style={{
        position: "absolute", inset: "-8px", borderRadius: "50%",
        background: `radial-gradient(circle, ${glow} 0%, transparent 70%)`,
        pointerEvents: "none",
      }} />
      <svg width="140" height="140" viewBox="0 0 140 140" className="score-ring">
        {/* Track */}
        <circle cx="70" cy="70" r={radius} fill="none"
          stroke="var(--bg-muted)" strokeWidth="10" />
        {/* Fill */}
        <circle
          cx="70" cy="70" r={radius} fill="none"
          stroke={color} strokeWidth="10"
          strokeDasharray={`${filled} ${circumference}`}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 1s ease" }}
        />
      </svg>
      <div style={{
        position: "absolute", inset: 0, display: "flex",
        flexDirection: "column", alignItems: "center", justifyContent: "center",
      }}>
        <span style={{ fontSize: "1.9rem", fontWeight: 800, color: "var(--text-primary)", lineHeight: 1 }}>
          {score}
        </span>
        <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 500 }}>% Real</span>
      </div>
    </div>
  );
}

export function ReportHeader({ verdict, jobId }: ReportHeaderProps) {
  const config = VERDICT_CONFIG[verdict.verdict_category] ?? VERDICT_CONFIG["Inconclusive"];

  const copyLink = () => {
    navigator.clipboard.writeText(window.location.href);
  };

  return (
    <div style={{
      background: "var(--bg-base)",
      border: "1px solid var(--border)",
      borderRadius: "var(--radius-2xl)",
      padding: "36px",
      boxShadow: "var(--shadow-lg)",
      position: "relative",
      overflow: "hidden",
    }}>
      {/* Decorative gradient strip */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: "4px",
        background: `linear-gradient(90deg, ${config.ringColor}, ${config.ringColor}88)`,
      }} />

      <div style={{ display: "flex", alignItems: "center", gap: "32px", flexWrap: "wrap" }}>
        {/* Score Ring */}
        <div style={{ flexShrink: 0 }}>
          <ScoreRing
            score={verdict.authenticity_score}
            color={config.ringColor}
            glow={config.glow}
          />
        </div>

        {/* Main content */}
        <div style={{ flex: 1, minWidth: "280px" }}>
          {/* Verdict badge */}
          <div style={{ marginBottom: "12px" }}>
            <span style={{
              display: "inline-flex", alignItems: "center", gap: "8px",
              padding: "6px 16px", borderRadius: "999px",
              background: config.bg, border: `1px solid ${config.border}`,
              color: config.text, fontWeight: 700, fontSize: "0.875rem",
            }}>
              <span style={{ color: config.ringColor }}>{config.icon}</span>
              {verdict.verdict_category}
            </span>
          </div>

          {/* Headline */}
          <h1 style={{
            fontSize: "1.5rem", fontWeight: 800, color: "var(--text-primary)",
            lineHeight: 1.3, margin: "0 0 12px",
          }}>
            {verdict.summary_headline}
          </h1>

          {/* C2PA status */}
          <div style={{
            display: "flex", alignItems: "center", gap: "8px",
            padding: "8px 14px", borderRadius: "var(--radius-md)",
            background: verdict.c2pa_status?.is_ai_generated ? "var(--rose-50)" : "var(--bg-subtle)",
            border: "1px solid var(--border)", marginBottom: "20px",
          }}>
            <Shield size={14} color={verdict.c2pa_status?.is_ai_generated ? "var(--rose-500)" : "var(--text-muted)"} />
            <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontWeight: 500 }}>
              C2PA:{" "}
              <strong style={{ color: verdict.c2pa_status?.is_ai_generated ? "#9f1239" : "var(--text-primary)" }}>
                {verdict.c2pa_status?.is_ai_generated
                  ? `AI-Generated (${verdict.c2pa_status.generator ?? "Unknown tool"})`
                  : verdict.c2pa_status?.status === "no_manifest"
                  ? "No Content Credentials"
                  : "Signed Authentic"}
              </strong>
            </span>
          </div>

          {/* Action buttons */}
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <button
              onClick={copyLink}
              style={{
                padding: "9px 18px", borderRadius: "var(--radius-md)",
                border: "1px solid var(--border)", background: "var(--bg-base)",
                cursor: "pointer", fontSize: "0.85rem", fontWeight: 600,
                color: "var(--text-secondary)", fontFamily: "Inter, sans-serif",
                display: "flex", alignItems: "center", gap: "6px",
                transition: "all 0.15s ease",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = "var(--bg-subtle)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = "var(--bg-base)";
              }}
            >
              🔗 Copy Shareable Link
            </button>
            <span style={{
              padding: "9px 14px", borderRadius: "var(--radius-md)",
              background: "var(--bg-subtle)", fontSize: "0.78rem",
              color: "var(--text-muted)", fontFamily: "JetBrains Mono, monospace",
              display: "flex", alignItems: "center",
            }}>
              ID: {jobId.slice(0, 8)}...
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
