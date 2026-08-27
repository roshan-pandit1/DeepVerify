"use client";

import {
  ShieldCheck,
  ShieldAlert,
  Activity,
  Eye,
  Brain,
  Link as LinkIcon,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types matching the backend final_result shape
// ---------------------------------------------------------------------------

interface TemporalMetrics {
  mean_fake_score: number;
  temporal_jitter: number;
  peak_frame_score: number;
  frames_analyzed: number;
}

interface VisualThreatMetrics {
  max_threat_score: number;
  flagged_content: string[];
  frames_analyzed: number;
}

interface PsychologicalMetrics {
  manipulation_score: number;
  detected_tactics: string[];
  reasoning: string;
}

interface ThreatMatrixProps {
  report: {
    temporal?: { is_manipulated?: boolean; metrics?: TemporalMetrics };
    visual_threat?: { is_visual_threat?: boolean; metrics?: VisualThreatMetrics };
    psychological_threat?: {
      is_psychological_threat?: boolean;
      metrics?: PsychologicalMetrics;
    };
    blockchain?: { tx_hash?: string };
  } | null;
}

// ---------------------------------------------------------------------------
// Status config helper
// ---------------------------------------------------------------------------

type StatusConfig = {
  bg: string;
  border: string;
  text: string;
  iconColor: string;
  Icon: typeof CheckCircle2;
};

function getStatusConfig(isThreat: boolean): StatusConfig {
  return isThreat
    ? {
        bg: "bg-rose-50",
        border: "border-rose-200",
        text: "text-rose-700",
        iconColor: "text-rose-500",
        Icon: AlertTriangle,
      }
    : {
        bg: "bg-emerald-50",
        border: "border-emerald-200",
        text: "text-emerald-700",
        iconColor: "text-emerald-500",
        Icon: CheckCircle2,
      };
}

// ---------------------------------------------------------------------------
// Metric row helper
// ---------------------------------------------------------------------------

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-500">{label}</span>
      <span className="font-semibold text-slate-700">{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tag chip helper
// ---------------------------------------------------------------------------

function Tag({
  label,
  variant,
}: {
  label: string;
  variant: "rose" | "amber" | "emerald";
}) {
  const styles = {
    rose: "bg-rose-100 text-rose-700 border-rose-200",
    amber: "bg-amber-100 text-amber-800 border-amber-200",
    emerald: "bg-emerald-100 text-emerald-700 border-emerald-200",
  };
  return (
    <span
      className={`px-2 py-1 text-xs rounded-md font-medium border ${styles[variant]}`}
    >
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function ThreatMatrix({ report }: ThreatMatrixProps) {
  if (!report) return null;

  const { temporal, visual_threat, psychological_threat, blockchain } = report;

  const isTemporalThreat = temporal?.is_manipulated ?? false;
  const isVisualThreat = visual_threat?.is_visual_threat ?? false;
  const isPsychThreat =
    psychological_threat?.is_psychological_threat ?? false;
  const isHighlySuspicious = isTemporalThreat || isPsychThreat;

  const temporalConfig = getStatusConfig(isTemporalThreat);
  const visualConfig = getStatusConfig(isVisualThreat);
  const psychConfig = getStatusConfig(isPsychThreat);

  const tm = temporal?.metrics;
  const vtm = visual_threat?.metrics;
  const pm = psychological_threat?.metrics;

  const txHash = blockchain?.tx_hash;

  return (
    <div className="space-y-6">
      {/* ── Header verdict banner ── */}
      <div
        className={`p-6 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4 shadow-lg transition-all duration-500 ${
          isHighlySuspicious
            ? "bg-rose-500 text-white"
            : "bg-emerald-600 text-white"
        }`}
      >
        <div className="flex items-center gap-4">
          {isHighlySuspicious ? (
            <ShieldAlert size={40} className="shrink-0" />
          ) : (
            <ShieldCheck size={40} className="shrink-0" />
          )}
          <div>
            <h2 className="text-2xl font-bold tracking-tight">
              {isHighlySuspicious
                ? "High-Risk Manipulative Content"
                : "Authentic & Safe"}
            </h2>
            <p className="text-sm opacity-80 font-medium mt-0.5">
              Multi-Modal Threat Synthesis — Pillars 1 · 2 · 3
            </p>
          </div>
        </div>

        {/* Blockchain badge */}
        {txHash && (
          <div className="flex items-center gap-2 bg-black/20 px-4 py-2 rounded-xl backdrop-blur-sm shrink-0">
            <LinkIcon size={15} />
            <div className="text-sm">
              <p className="font-semibold text-white/90 leading-tight">
                Sealed on Celo Sepolia
              </p>
              <a
                href={`https://sepolia.celoscan.io/tx/${txHash}`}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-white/60 hover:text-white underline decoration-white/30 transition-colors"
              >
                View on-chain certificate →
              </a>
            </div>
          </div>
        )}
      </div>

      {/* ── 3-pillar grid ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">

        {/* Pillar 1 — Temporal Integrity */}
        <div
          className={`p-5 rounded-xl border shadow-sm flex flex-col transition-shadow hover:shadow-md ${temporalConfig.bg} ${temporalConfig.border}`}
        >
          <div className="flex items-center justify-between mb-4">
            <div className={`p-2 rounded-lg bg-white shadow-sm ${temporalConfig.iconColor}`}>
              <Activity size={22} />
            </div>
            <temporalConfig.Icon size={19} className={temporalConfig.iconColor} />
          </div>

          <h3 className={`font-bold text-base ${temporalConfig.text}`}>
            Pillar 1 · Temporal Integrity
          </h3>
          <p className="text-xs text-slate-500 mt-1 mb-4 leading-relaxed">
            Frame-to-frame deepfake flickering and AI blending errors over the
            video timeline.
          </p>

          <div className="mt-auto space-y-2 text-sm bg-white/60 p-3 rounded-lg border border-black/5">
            {tm ? (
              <>
                <MetricRow
                  label="Mean Suspicion"
                  value={`${(tm.mean_fake_score * 100).toFixed(1)}%`}
                />
                <MetricRow
                  label="Temporal Jitter"
                  value={`${(tm.temporal_jitter * 100).toFixed(1)}%`}
                />
                <MetricRow
                  label="Peak Anomaly"
                  value={`${(tm.peak_frame_score * 100).toFixed(1)}%`}
                />
                <MetricRow
                  label="Frames Analyzed"
                  value={String(tm.frames_analyzed)}
                />
              </>
            ) : (
              <p className="text-slate-400 text-xs">No data available</p>
            )}
          </div>
        </div>

        {/* Pillar 2 — Visual Safety */}
        <div
          className={`p-5 rounded-xl border shadow-sm flex flex-col transition-shadow hover:shadow-md ${visualConfig.bg} ${visualConfig.border}`}
        >
          <div className="flex items-center justify-between mb-4">
            <div className={`p-2 rounded-lg bg-white shadow-sm ${visualConfig.iconColor}`}>
              <Eye size={22} />
            </div>
            <visualConfig.Icon size={19} className={visualConfig.iconColor} />
          </div>

          <h3 className={`font-bold text-base ${visualConfig.text}`}>
            Pillar 2 · Visual Safety
          </h3>
          <p className="text-xs text-slate-500 mt-1 mb-4 leading-relaxed">
            CLIP zero-shot scan for graphic violence, riots, or armed conflict
            imagery.
          </p>

          <div className="mt-auto space-y-2 text-sm bg-white/60 p-3 rounded-lg border border-black/5">
            {vtm ? (
              <>
                <MetricRow
                  label="Threat Confidence"
                  value={`${(vtm.max_threat_score * 100).toFixed(1)}%`}
                />
                <MetricRow
                  label="Frames Scanned"
                  value={String(vtm.frames_analyzed)}
                />
                <div className="pt-1">
                  <span className="text-slate-500 block mb-1.5">
                    Detected flags:
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {vtm.flagged_content.length > 0 ? (
                      vtm.flagged_content.map((flag, idx) => (
                        <Tag key={idx} label={flag} variant="rose" />
                      ))
                    ) : (
                      <Tag label="Clean" variant="emerald" />
                    )}
                  </div>
                </div>
              </>
            ) : (
              <p className="text-slate-400 text-xs">No data available</p>
            )}
          </div>
        </div>

        {/* Pillar 3 — Cognitive Security */}
        <div
          className={`p-5 rounded-xl border shadow-sm flex flex-col transition-shadow hover:shadow-md ${psychConfig.bg} ${psychConfig.border}`}
        >
          <div className="flex items-center justify-between mb-4">
            <div className={`p-2 rounded-lg bg-white shadow-sm ${psychConfig.iconColor}`}>
              <Brain size={22} />
            </div>
            <psychConfig.Icon size={19} className={psychConfig.iconColor} />
          </div>

          <h3 className={`font-bold text-base ${psychConfig.text}`}>
            Pillar 3 · Cognitive Security
          </h3>
          <p className="text-xs text-slate-500 mt-1 mb-4 leading-relaxed">
            LLM analysis of rhetoric for propaganda, fear-mongering, and
            societal manipulation tactics.
          </p>

          <div className="mt-auto space-y-2 text-sm bg-white/60 p-3 rounded-lg border border-black/5">
            {pm ? (
              <>
                <MetricRow
                  label="Manipulation Score"
                  value={`${(pm.manipulation_score * 100).toFixed(1)}%`}
                />
                <div className="pt-1">
                  <span className="text-slate-500 block mb-1.5">
                    Detected tactics:
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {pm.detected_tactics.length > 0 ? (
                      pm.detected_tactics.map((tactic, idx) => (
                        <Tag key={idx} label={tactic} variant="amber" />
                      ))
                    ) : (
                      <Tag label="None detected" variant="emerald" />
                    )}
                  </div>
                </div>
              </>
            ) : (
              <p className="text-slate-400 text-xs">No data available</p>
            )}
          </div>
        </div>
      </div>

      {/* ── Analyst reasoning note ── */}
      {pm?.reasoning && (
        <div className="p-5 rounded-xl border border-slate-200 bg-slate-50 animate-fade-in-up">
          <h4 className="font-semibold text-slate-800 mb-2 flex items-center gap-2 text-sm">
            <Brain size={16} className="text-slate-400" />
            Psychological Analyst Notes
          </h4>
          <p className="text-slate-600 text-sm leading-relaxed">{pm.reasoning}</p>
        </div>
      )}
    </div>
  );
}
