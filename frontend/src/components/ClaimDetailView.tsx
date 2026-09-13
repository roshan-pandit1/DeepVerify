"use client";

import React from "react";
import { CheckCircle2, Tag, FileText, Calendar } from "lucide-react";

interface Assertion {
  id: string;
  assertion_text: string;
  entities: string[];
  confidence_weight: number;
}

interface ClaimDetailViewProps {
  claim: {
    id: string;
    raw_input: string;
    normalized_text?: string;
    status: string;
    created_at: string;
    assertions?: Assertion[];
  };
}

export const ClaimDetailView: React.FC<ClaimDetailViewProps> = ({ claim }) => {
  return (
    <div className="w-full bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-indigo-500/10 text-indigo-400 rounded-lg border border-indigo-500/20">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Claim Investigation #{claim.id.slice(0, 8)}</h3>
            <div className="flex items-center space-x-2 text-xs text-slate-400 mt-0.5">
              <Calendar className="w-3.5 h-3.5" />
              <span>{new Date(claim.created_at).toLocaleString()}</span>
            </div>
          </div>
        </div>
        <span className={`px-3 py-1 text-xs font-semibold rounded-full border uppercase tracking-wider ${
          claim.status === "completed" ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/60" : "bg-amber-950/60 text-amber-400 border-amber-800/60 animate-pulse"
        }`}>
          {claim.status}
        </span>
      </div>

      <div>
        <h4 className="text-xs uppercase font-bold tracking-wider text-slate-400 mb-2">Original Submission</h4>
        <p className="bg-slate-950/80 p-4 rounded-xl text-slate-200 text-sm border border-slate-850 leading-relaxed font-mono">
          {claim.raw_input}
        </p>
      </div>

      {claim.normalized_text && (
        <div>
          <h4 className="text-xs uppercase font-bold tracking-wider text-slate-400 mb-2">Normalized Claim Unit</h4>
          <p className="bg-slate-950/80 p-4 rounded-xl text-slate-300 text-sm border border-slate-850 leading-relaxed">
            {claim.normalized_text}
          </p>
        </div>
      )}

      {claim.assertions && claim.assertions.length > 0 && (
        <div>
          <h4 className="text-xs uppercase font-bold tracking-wider text-slate-400 mb-3">Extracted Sub-Assertions & Entities</h4>
          <div className="space-y-3">
            {claim.assertions.map((a, i) => (
              <div key={a.id || i} className="bg-slate-950/50 p-4 rounded-xl border border-slate-800 space-y-2">
                <div className="flex items-start space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
                  <span className="text-sm text-white font-medium">{a.assertion_text}</span>
                </div>
                {a.entities && a.entities.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    <Tag className="w-3.5 h-3.5 text-slate-400" />
                    {a.entities.map((e, idx) => (
                      <span key={idx} className="bg-blue-950/60 text-blue-300 border border-blue-800/40 text-[11px] px-2 py-0.5 rounded-md font-medium">
                        {e}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
