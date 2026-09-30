"use client";

import React from "react";
import { ShieldCheck, AlertTriangle, XCircle, HelpCircle, Award } from "lucide-react";

export interface VerdictReport {
  id: string;
  claim_id: string;
  verdict: "Verified" | "Uncertain" | "Unsupported" | "Contested" | string;
  confidence_score: number;
  summary_explanation: string;
  evidence_items: any[];
  completed_at: string;
}

const VERDICT_THEMES: Record<string, { icon: React.ReactNode; bg: string; border: string; text: string; bar: string }> = {
  Verified: {
    icon: <ShieldCheck size={26} className="text-emerald-600" />,
    bg: "#ecfdf5",
    border: "#a7f3d0",
    text: "#065f46",
    bar: "#10b981",
  },
  Unsupported: {
    icon: <XCircle size={26} className="text-red-600" />,
    bg: "#fef2f2",
    border: "#fecaca",
    text: "#991b1b",
    bar: "#ef4444",
  },
  Contested: {
    icon: <AlertTriangle size={26} className="text-amber-600" />,
    bg: "#fffbeb",
    border: "#fde68a",
    text: "#92400e",
    bar: "#f59e0b",
  },
  Uncertain: {
    icon: <HelpCircle size={26} className="text-blue-600" />,
    bg: "#eff6ff",
    border: "#bfdbfe",
    text: "#1e40af",
    bar: "#3b82f6",
  },
};

export function VerdictSection({ verdict }: { verdict: VerdictReport }) {
  const theme = VERDICT_THEMES[verdict.verdict] || VERDICT_THEMES.Uncertain;

  return (
    <section className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <Award size={18} className="text-blue-600" />
        <h2 className="text-lg font-bold text-slate-900">Section 1: Forensic Verdict Report</h2>
      </div>

      <div
        className="flash-card p-6"
        style={{ backgroundColor: theme.bg, borderColor: theme.border }}
      >
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-white flex items-center justify-center shadow-sm">
              {theme.icon}
            </div>
            <div>
              <span className="text-xs font-bold uppercase tracking-wider opacity-80" style={{ color: theme.text }}>
                Final Classification
              </span>
              <h3 className="text-2xl font-black mt-0.5" style={{ color: theme.text }}>
                {verdict.verdict}
              </h3>
            </div>
          </div>

          {/* Confidence Meter */}
          <div className="bg-white border rounded-xl px-4 py-2 text-right shadow-sm" style={{ borderColor: theme.border }}>
            <span className="text-xs text-slate-500 font-semibold uppercase">Confidence</span>
            <div className="text-2xl font-black" style={{ color: theme.text }}>
              {verdict.confidence_score.toFixed(0)}%
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full h-2.5 bg-black/10 rounded-full overflow-hidden mb-4">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{ width: `${verdict.confidence_score}%`, backgroundColor: theme.bar }}
          />
        </div>

        {/* Rationale */}
        <div className="bg-white p-4 rounded-xl border shadow-sm" style={{ borderColor: theme.border }}>
          <span className="text-xs font-bold text-slate-500 uppercase">AI Analytical Rationale</span>
          <p className="mt-1 text-sm text-slate-800 leading-relaxed font-medium">
            {verdict.summary_explanation}
          </p>
        </div>
      </div>
    </section>
  );
}
