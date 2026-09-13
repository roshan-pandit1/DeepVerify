"use client";

import React from "react";
import { History, Clock, Activity } from "lucide-react";

export interface AuditLogEntry {
  id: string;
  claim_id: string;
  stage_name: string;
  input_summary: string;
  output_summary: string;
  execution_time_ms: number;
  timestamp: string;
}

interface AuditTrailViewerProps {
  entries: AuditLogEntry[];
}

export const AuditTrailViewer: React.FC<AuditTrailViewerProps> = ({ entries }) => {
  if (!entries || entries.length === 0) {
    return null;
  }

  return (
    <div className="w-full bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-6">
      <div className="flex items-center space-x-3 pb-4 border-b border-slate-800">
        <div className="p-2 bg-indigo-600/20 text-indigo-400 rounded-xl border border-indigo-500/30">
          <History className="w-5 h-5" />
        </div>
        <div>
          <h3 className="text-lg font-bold text-white tracking-wide">Verification Audit Trail</h3>
          <p className="text-xs text-slate-400">Step-by-step immutable execution logs and timing metrics</p>
        </div>
      </div>

      <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
        {entries.map((entry, index) => (
          <div key={entry.id || index} className="relative group">
            <div className="absolute -left-6 top-1.5 w-3 h-3 rounded-full bg-blue-500 border-2 border-slate-900 group-hover:scale-125 transition-transform" />

            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-2 hover:border-slate-700 transition-colors">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center space-x-2">
                  <Activity className="w-4 h-4 text-blue-400" />
                  <span className="text-xs font-bold text-white tracking-wider uppercase">{entry.stage_name}</span>
                </div>
                <div className="flex items-center space-x-3 text-[11px] text-slate-400">
                  <div className="flex items-center space-x-1">
                    <Clock className="w-3 h-3 text-slate-500" />
                    <span>{entry.execution_time_ms} ms</span>
                  </div>
                  <span>{new Date(entry.timestamp).toLocaleTimeString()}</span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-2 border-t border-slate-900/60 text-xs">
                <div>
                  <span className="text-slate-500 font-semibold uppercase text-[10px] block">Stage Input</span>
                  <p className="text-slate-300 font-mono mt-0.5">{entry.input_summary}</p>
                </div>
                <div>
                  <span className="text-slate-500 font-semibold uppercase text-[10px] block">Stage Output</span>
                  <p className="text-slate-300 font-mono mt-0.5">{entry.output_summary}</p>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
