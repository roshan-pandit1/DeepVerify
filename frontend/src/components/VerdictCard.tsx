"use client";

import React from "react";
import { ShieldCheck, AlertTriangle, XCircle, HelpCircle, ExternalLink, Award } from "lucide-react";

export interface EvidenceItem {
  id: string;
  source_name: string;
  source_url?: string;
  content_snippet: string;
  stance: "supports" | "refutes" | "neutral";
  credibility_score: number;
}

export interface VerdictReport {
  id: string;
  claim_id: string;
  verdict: "Verified" | "Uncertain" | "Unsupported" | "Contested";
  confidence_score: number;
  summary_explanation: string;
  evidence_items: EvidenceItem[];
  completed_at: string;
}

interface VerdictCardProps {
  report: VerdictReport;
}

export const VerdictCard: React.FC<VerdictCardProps> = ({ report }) => {
  const getBadgeStyle = (verdict: string) => {
    switch (verdict) {
      case "Verified":
        return {
          icon: <ShieldCheck className="w-6 h-6 text-emerald-400" />,
          bg: "bg-emerald-950/80 border-emerald-800/80 text-emerald-300",
          barBg: "bg-emerald-500",
        };
      case "Unsupported":
        return {
          icon: <XCircle className="w-6 h-6 text-rose-400" />,
          bg: "bg-rose-950/80 border-rose-800/80 text-rose-300",
          barBg: "bg-rose-500",
        };
      case "Contested":
        return {
          icon: <AlertTriangle className="w-6 h-6 text-amber-400" />,
          bg: "bg-amber-950/80 border-amber-800/80 text-amber-300",
          barBg: "bg-amber-500",
        };
      default:
        return {
          icon: <HelpCircle className="w-6 h-6 text-slate-400" />,
          bg: "bg-slate-900/80 border-slate-800/80 text-slate-300",
          barBg: "bg-blue-500",
        };
    }
  };

  const style = getBadgeStyle(report.verdict);

  return (
    <div className="w-full space-y-6">
      {/* Verdict Summary Card */}
      <div className={`p-6 rounded-2xl border backdrop-blur-md shadow-2xl space-y-5 ${style.bg}`}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-slate-950/60 rounded-xl border border-slate-800">
              {style.icon}
            </div>
            <div>
              <div className="text-xs uppercase font-bold tracking-widest opacity-75">Verification Classification</div>
              <h3 className="text-2xl font-black tracking-wide text-white">{report.verdict}</h3>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs uppercase font-bold tracking-widest opacity-75">Confidence Index</div>
            <div className="text-2xl font-black text-white">{report.confidence_score}%</div>
          </div>
        </div>

        {/* Progress meter */}
        <div className="w-full bg-slate-950/80 h-2.5 rounded-full overflow-hidden p-0.5 border border-slate-800">
          <div
            className={`h-full rounded-full transition-all duration-700 ${style.barBg}`}
            style={{ width: `${report.confidence_score}%` }}
          />
        </div>

        <p className="text-sm text-slate-200 leading-relaxed bg-slate-950/40 p-4 rounded-xl border border-slate-800/40 font-medium">
          {report.summary_explanation}
        </p>
      </div>

      {/* Evidence Sources Breakdown */}
      {report.evidence_items && report.evidence_items.length > 0 && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
          <h4 className="text-sm uppercase font-bold tracking-wider text-slate-400 flex items-center space-x-2">
            <Award className="w-4 h-4 text-blue-400" />
            <span>Corroborating OSINT & Source Evidence ({report.evidence_items.length})</span>
          </h4>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {report.evidence_items.map((ev) => (
              <div key={ev.id} className="bg-slate-950/70 p-4 rounded-xl border border-slate-850 flex flex-col justify-between space-y-3">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-blue-400 tracking-wide uppercase">{ev.source_name}</span>
                    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-md border ${
                      ev.stance === "supports" ? "bg-emerald-950/70 text-emerald-300 border-emerald-800/60" :
                      ev.stance === "refutes" ? "bg-rose-950/70 text-rose-300 border-rose-800/60" : "bg-slate-800 text-slate-300 border-slate-700"
                    }`}>
                      {ev.stance}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 italic line-clamp-3 leading-relaxed">
                    "{ev.content_snippet}"
                  </p>
                </div>

                <div className="pt-2 border-t border-slate-900 flex items-center justify-between text-[11px] text-slate-400">
                  <span>Credibility: <strong className="text-white">{(ev.credibility_score * 100).toFixed(0)}%</strong></span>
                  {ev.source_url && (
                    <a
                      href={ev.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center space-x-1 text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      <span>Source</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
