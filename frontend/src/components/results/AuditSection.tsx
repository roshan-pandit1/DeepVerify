"use client";

import React from "react";
import { History } from "lucide-react";

export interface AuditLogEntry {
  id: string;
  claim_id: string;
  stage_name: string;
  input_summary: string;
  output_summary: string;
  execution_time_ms: number;
  timestamp: string;
}

export function AuditSection({ logs }: { logs: AuditLogEntry[] }) {
  return (
    <section className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <History size={18} className="text-blue-600" />
        <h2 className="text-lg font-bold text-slate-900">
          Section 4: Verification Pipeline Audit Trail ({logs.length} Stages)
        </h2>
      </div>

      <div className="card-box p-6">
        {logs.length > 0 ? (
          <div className="relative pl-6 flex flex-col gap-4">
            <div className="absolute left-2.5 top-2 bottom-2 w-0.5 bg-slate-200" />

            {logs.map((log, idx) => (
              <div key={log.id || idx} className="relative">
                <div className="absolute -left-5 top-1.5 w-3 h-3 rounded-full bg-blue-600 border-2 border-white shadow-sm ring-2 ring-blue-100" />

                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3.5 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="font-extrabold text-slate-900">{log.stage_name}</span>
                      <span className="bg-slate-200 text-slate-700 px-1.5 py-0.5 rounded font-mono font-bold">
                        {log.execution_time_ms}ms
                      </span>
                    </div>
                    <span className="text-slate-400">{new Date(log.timestamp).toLocaleTimeString()}</span>
                  </div>

                  <div className="space-y-1 text-slate-600">
                    <p><strong className="text-slate-700">In:</strong> {log.input_summary}</p>
                    <p><strong className="text-slate-900">Out:</strong> {log.output_summary}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-400 italic text-center py-4">No audit logs recorded.</p>
        )}
      </div>
    </section>
  );
}
