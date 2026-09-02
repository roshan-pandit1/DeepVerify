"use client";

import React from 'react';
import { 
  AlertTriangle, 
  ShieldCheck, 
  Users, 
  Flame, 
  CheckCircle2, 
  Info,
  Radio
} from 'lucide-react';

export interface CrowdAnalysisData {
  debunk_consensus: number; // 0.0 to 1.0
  societal_panic_index: number; // 0 to 100
  extracted_claims: string[];
  comments_analyzed: number;
  priority_threat: boolean;
  error?: string | null;
}

interface CrowdOsintRadarProps {
  data?: CrowdAnalysisData;
}

export const CrowdOsintRadar: React.FC<CrowdOsintRadarProps> = ({ data }) => {
  if (!data) {
    return (
      <div className="bg-white border-2 border-dotted border-black rounded-xl p-6 text-slate-500 text-center animate-pulse">
        Waiting for Social Context & Crowd OSINT ingestion...
      </div>
    );
  }

  const {
    debunk_consensus = 0.5,
    societal_panic_index = 0,
    extracted_claims = [],
    comments_analyzed = 0,
    priority_threat = false,
  } = data;

  const debunkPercent = Math.round(debunk_consensus * 100);

  // Dynamic Panic Severity Styling
  const getPanicBadge = (panic: number) => {
    if (panic >= 75) {
      return {
        label: 'CRITICAL / PANIC ELEVATED',
        badgeClass: 'bg-rose-50 text-rose-700 border-rose-400',
        barColor: 'bg-rose-500',
        textColor: 'text-rose-600',
      };
    }
    if (panic >= 40) {
      return {
        label: 'MODERATE TENSION',
        badgeClass: 'bg-amber-50 text-amber-700 border-amber-400',
        barColor: 'bg-amber-500',
        textColor: 'text-amber-600',
      };
    }
    return {
      label: 'STABLE / LOW CONVERSATIONAL ANXIETY',
      badgeClass: 'bg-sky-50 text-sky-700 border-sky-400',
      barColor: 'bg-sky-500',
      textColor: 'text-sky-600',
    };
  };

  // Dynamic Debunk Severity Styling
  const getDebunkStatus = (score: number) => {
    if (score >= 0.75) {
      return {
        label: 'High Debunk Consensus (Suspect Fabricated)',
        textColor: 'text-rose-600',
        barColor: 'bg-rose-500',
      };
    }
    if (score <= 0.35) {
      return {
        label: 'Crowd Considers Likely Authentic',
        textColor: 'text-emerald-600',
        barColor: 'bg-emerald-500',
      };
    }
    return {
      label: 'Divided / Unverified Crowd Sentiment',
      textColor: 'text-amber-600',
      barColor: 'bg-amber-500',
    };
  };

  const panicInfo = getPanicBadge(societal_panic_index);
  const debunkInfo = getDebunkStatus(debunk_consensus);

  return (
    <div className="bg-white border-2 border-dotted border-black rounded-2xl p-6 text-slate-900 shadow-md relative overflow-hidden">
      {/* Header Section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-5 border-b border-dotted border-black/40">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-sky-50 border border-dotted border-sky-400 rounded-xl text-sky-600">
            <Radio className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h3 className="font-semibold text-lg text-slate-900 flex items-center gap-2">
              Social Context & Crowd OSINT Radar
            </h3>
            <p className="text-xs text-slate-600 flex items-center gap-1 mt-0.5">
              <Users className="w-3.5 h-3.5 text-slate-500" />
              Ingested & sanitized <span className="text-slate-900 font-semibold">{comments_analyzed}</span> user reactions
            </p>
          </div>
        </div>

        {/* Priority Status Pill */}
        {priority_threat ? (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide border border-dotted bg-rose-50 text-rose-700 border-rose-500 uppercase animate-pulse">
            <AlertTriangle className="w-4 h-4" />
            Priority Threat Escalated
          </div>
        ) : (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide border border-dotted bg-slate-100 text-slate-800 border-black/60 uppercase">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            Standard Triage Routing
          </div>
        )}
      </div>

      {/* Dual Analytical Gauges */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 my-6">
        
        {/* Metric 1: Debunk Consensus */}
        <div className="bg-slate-50 border border-dotted border-black/40 rounded-xl p-4.5 flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-start mb-2">
              <span className="text-xs uppercase font-medium tracking-wider text-slate-600">
                Debunk Consensus
              </span>
              <span className={`text-xl font-bold font-mono ${debunkInfo.textColor}`}>
                {debunkPercent}%
              </span>
            </div>
            
            {/* Progress Bar Track */}
            <div className="w-full h-2.5 bg-slate-200 rounded-full overflow-hidden mb-2 border border-slate-300">
              <div 
                className={`h-full transition-all duration-500 ${debunkInfo.barColor}`} 
                style={{ width: `${debunkPercent}%` }} 
              />
            </div>
          </div>
          <p className="text-xs text-slate-600 flex items-center gap-1.5 mt-2">
            <Info className="w-3.5 h-3.5 shrink-0 text-slate-500" />
            <span>{debunkInfo.label}</span>
          </p>
        </div>

        {/* Metric 2: Societal Panic Index */}
        <div className="bg-slate-50 border border-dotted border-black/40 rounded-xl p-4.5 flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-start mb-2">
              <span className="text-xs uppercase font-medium tracking-wider text-slate-600 flex items-center gap-1.5">
                <Flame className="w-3.5 h-3.5 text-amber-500" />
                Societal Panic Index
              </span>
              <span className={`text-xl font-bold font-mono ${panicInfo.textColor}`}>
                {societal_panic_index}<span className="text-xs text-slate-500 font-normal">/100</span>
              </span>
            </div>

            {/* Progress Bar Track */}
            <div className="w-full h-2.5 bg-slate-200 rounded-full overflow-hidden mb-2 border border-slate-300">
              <div 
                className={`h-full transition-all duration-500 ${panicInfo.barColor}`} 
                style={{ width: `${societal_panic_index}%` }} 
              />
            </div>
          </div>
          <p className="text-xs text-slate-600 flex items-center gap-1.5 mt-2">
            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border border-dotted ${panicInfo.badgeClass}`}>
              {panicInfo.label}
            </span>
          </p>
        </div>

      </div>

      {/* Extracted Factual Assertions & Debunk Signals */}
      <div className="mt-2">
        <h4 className="text-xs uppercase tracking-wider font-semibold text-slate-700 mb-3 flex items-center gap-1.5">
          <CheckCircle2 className="w-4 h-4 text-sky-600" />
          Factual Assertions & Crowd Citations Extracted
        </h4>

        {extracted_claims.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {extracted_claims.map((claim, idx) => (
              <span 
                key={idx}
                className="inline-flex items-center text-xs bg-slate-100 hover:bg-slate-200 border border-dotted border-black/50 text-slate-900 px-3 py-1.5 rounded-lg transition-colors"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-sky-500 mr-2 shrink-0" />
                {claim}
              </span>
            ))}
          </div>
        ) : (
          <div className="bg-slate-50 border border-dotted border-black/30 rounded-lg p-3 text-xs text-slate-500 italic">
            No specific external dates, sources, or archival citations were pinpointed by commentators.
          </div>
        )}
      </div>

    </div>
  );
};
