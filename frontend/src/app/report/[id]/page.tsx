"use client";

import React, { useState, useEffect, use } from "react";
import { ClaimDetailView } from "@/components/ClaimDetailView";
import { VerdictCard, VerdictReport } from "@/components/VerdictCard";
import { AuditTrailViewer, AuditLogEntry } from "@/components/AuditTrailViewer";
import { Shield, ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const claimId = resolvedParams.id;

  const [claimDetail, setClaimDetail] = useState<any>(null);
  const [verdictReport, setVerdictReport] = useState<VerdictReport | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [claimRes, verdictRes, auditRes] = await Promise.all([
          fetch(`http://localhost:8000/api/v1/claims/${claimId}`),
          fetch(`http://localhost:8000/api/v1/claims/${claimId}/verdict`),
          fetch(`http://localhost:8000/api/v1/claims/${claimId}/audit-trail`),
        ]);

        if (claimRes.ok) setClaimDetail(await claimRes.json());
        if (verdictRes.status === 200) setVerdictReport(await verdictRes.json());
        if (auditRes.ok) setAuditLogs(await auditRes.json());
      } catch (err) {
        console.error("Failed to load report data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [claimId]);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8 space-y-8">
      <header className="max-w-4xl mx-auto flex items-center justify-between pb-6 border-b border-slate-850">
        <Link href="/" className="flex items-center space-x-2 text-sm text-slate-400 hover:text-white transition-colors">
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Verification Hub</span>
        </Link>

        <div className="flex items-center space-x-2">
          <Shield className="w-5 h-5 text-blue-500" />
          <span className="font-bold text-white">DeepVerify Report</span>
        </div>
      </header>

      <div className="max-w-4xl mx-auto space-y-6">
        {loading ? (
          <div className="text-center py-12 space-y-3">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-sm text-slate-400">Loading verification report audit trail...</p>
          </div>
        ) : (
          <>
            {claimDetail && <ClaimDetailView claim={claimDetail} />}
            {verdictReport && <VerdictCard report={verdictReport} />}
            {auditLogs && auditLogs.length > 0 && <AuditTrailViewer entries={auditLogs} />}
          </>
        )}
      </div>
    </main>
  );
}
