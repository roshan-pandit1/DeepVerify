"use client";

import React, { useState, useEffect } from "react";
import { ClaimSubmissionForm } from "@/components/ClaimSubmissionForm";
import { ClaimDetailView } from "@/components/ClaimDetailView";
import { VerdictCard, VerdictReport } from "@/components/VerdictCard";
import { AuditTrailViewer, AuditLogEntry } from "@/components/AuditTrailViewer";
import { Shield, Sparkles, RefreshCw } from "lucide-react";

export default function Home() {
  const [activeClaimId, setActiveClaimId] = useState<string | null>(null);
  const [claimDetail, setClaimDetail] = useState<any>(null);
  const [verdictReport, setVerdictReport] = useState<VerdictReport | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchClaimData = async (claimId: string) => {
    try {
      setLoading(true);
      // 1. Fetch claim details & extracted assertions
      const claimRes = await fetch(`http://localhost:8000/api/v1/claims/${claimId}`);
      if (claimRes.ok) {
        const cData = await claimRes.json();
        setClaimDetail(cData);
      }

      // 2. Fetch verdict report
      const verdictRes = await fetch(`http://localhost:8000/api/v1/claims/${claimId}/verdict`);
      if (verdictRes.status === 200) {
        const vData = await verdictRes.json();
        setVerdictReport(vData);
      }

      // 3. Fetch audit logs
      const auditRes = await fetch(`http://localhost:8000/api/v1/claims/${claimId}/audit-trail`);
      if (auditRes.ok) {
        const aData = await auditRes.json();
        setAuditLogs(aData);
      }
    } catch (err) {
      console.error("Error fetching claim data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeClaimId) {
      fetchClaimData(activeClaimId);
      const interval = setInterval(() => fetchClaimData(activeClaimId), 3000);
      return () => clearInterval(interval);
    }
  }, [activeClaimId]);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 font-sans p-4 md:p-8 space-y-8">
      {/* Header Banner */}
      <header className="max-w-4xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 pb-6 border-b border-slate-850">
        <div className="flex items-center space-x-3">
          <div className="p-3 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-2xl shadow-xl">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-black tracking-tight text-white">
              DeepVerify <span className="text-blue-500 font-normal">Engine</span>
            </h1>
            <p className="text-xs md:text-sm text-slate-400">AI & OSINT Narrative Verification Platform</p>
          </div>
        </div>
      </header>

      {/* Main Submission Form */}
      <div className="max-w-4xl mx-auto">
        <ClaimSubmissionForm onClaimSubmitted={(id) => setActiveClaimId(id)} />
      </div>

      {/* Investigation Dashboard */}
      {activeClaimId && (
        <div className="max-w-4xl mx-auto space-y-6 pt-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-white flex items-center space-x-2">
              <Sparkles className="w-5 h-5 text-blue-400" />
              <span>Live Verification Report</span>
            </h2>
            <button
              onClick={() => fetchClaimData(activeClaimId)}
              className="flex items-center space-x-1 text-xs text-slate-400 hover:text-white bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              <span>Refresh</span>
            </button>
          </div>

          {claimDetail && <ClaimDetailView claim={claimDetail} />}

          {verdictReport && <VerdictCard report={verdictReport} />}

          {auditLogs && auditLogs.length > 0 && <AuditTrailViewer entries={auditLogs} />}
        </div>
      )}
    </main>
  );
}
