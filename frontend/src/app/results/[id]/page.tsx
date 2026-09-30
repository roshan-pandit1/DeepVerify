"use client";

import React, { useState, useEffect, use } from "react";
import Link from "next/link";
import {
  Shield,
  ArrowLeft,
  Copy,
  Check,
  Printer,
  Calendar,
  Clock,
  Layers,
  Award,
  FileText,
  Globe,
  History,
  RefreshCw,
  AlertTriangle,
} from "lucide-react";
import { VerdictSection, VerdictReport } from "@/components/results/VerdictSection";
import { ClaimSection, ClaimDetail } from "@/components/results/ClaimSection";
import { EvidenceSection } from "@/components/results/EvidenceSection";
import { AuditSection, AuditLogEntry } from "@/components/results/AuditSection";

export default function ResultsPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const claimId = resolvedParams.id;

  const [claim, setClaim] = useState<ClaimDetail | null>(null);
  const [verdict, setVerdict] = useState<VerdictReport | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [tab, setTab] = useState<"all" | "verdict" | "claim" | "evidence" | "audit">("all");

  const fetchData = async () => {
    try {
      const [cRes, vRes, aRes] = await Promise.all([
        fetch(`http://localhost:8000/api/v1/claims/${claimId}`),
        fetch(`http://localhost:8000/api/v1/claims/${claimId}/verdict`),
        fetch(`http://localhost:8000/api/v1/claims/${claimId}/audit-trail`),
      ]);
      if (cRes.ok) setClaim(await cRes.json());
      if (vRes.status === 200) setVerdict(await vRes.json());
      if (aRes.ok) setAuditLogs(await aRes.json());
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load report.");
    }
  };

  useEffect(() => {
    fetchData();
    const timer = setInterval(() => {
      if (!verdict && claim?.status !== "failed") fetchData();
    }, 2500);
    return () => clearInterval(timer);
  }, [claimId, verdict?.id, claim?.status]);

  const handleCopy = () => {
    if (typeof window !== "undefined") {
      navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const isComplete = claim?.status === "completed" && verdict !== null;
  const isProcessing = !isComplete && claim?.status !== "failed";

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      {/* Top Navbar */}
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="btn-secondary text-xs">
              <ArrowLeft size={13} /> Back
            </Link>
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white">
              <Shield size={16} />
            </div>
            <span className="font-extrabold text-slate-900 text-sm sm:text-base">
              Deep<span className="text-blue-600">Verify</span> / Report
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button onClick={handleCopy} className="btn-secondary text-xs">
              {copied ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
              {copied ? "Copied!" : "Share"}
            </button>
            <button onClick={() => window.print()} className="btn-secondary text-xs">
              <Printer size={12} /> Print
            </button>
            <Link href="/" className="btn-primary text-xs py-1.5 px-3">
              <RefreshCw size={12} /> New Scan
            </Link>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-6 py-6 flex-1 w-full">
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-center gap-2">
            <AlertTriangle size={15} /> {error}
          </div>
        )}

        {/* Case Banner */}
        <div className="card-box p-5 mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-semibold">
                CASE #{claimId.slice(0, 8)}
              </span>
              <span
                className={`badge-pill text-xs ${
                  isComplete ? "bg-emerald-100 text-emerald-700" : "bg-blue-100 text-blue-700"
                }`}
              >
                {isComplete ? "Completed" : "Processing"}
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-black text-slate-900">
              Narrative Authenticity Report
            </h1>
            {claim?.created_at && (
              <span className="text-xs text-slate-400 mt-1 flex items-center gap-1">
                <Calendar size={12} /> {new Date(claim.created_at).toLocaleString()}
              </span>
            )}
          </div>

          {/* Quick Counter */}
          {verdict && (
            <div className="flex items-center gap-4 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2 text-center text-xs">
              <div>
                <span className="text-slate-400 block font-medium">Sources</span>
                <strong className="text-slate-800 text-sm">{verdict.evidence_items.length}</strong>
              </div>
              <div className="w-px h-6 bg-slate-200" />
              <div>
                <span className="text-slate-400 block font-medium">Confidence</span>
                <strong className="text-blue-600 text-sm">{verdict.confidence_score.toFixed(0)}%</strong>
              </div>
            </div>
          )}
        </div>

        {/* Processing Stepper */}
        {isProcessing && (
          <div className="card-box p-8 text-center mb-6">
            <div className="w-10 h-10 border-3 border-slate-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-3" />
            <h2 className="text-base font-bold text-slate-900">Running Multi-Stage Verification...</h2>
            <p className="text-xs text-slate-500 mt-1">
              Decomposing claims, searching OSINT sources, and computing veracity verdict.
            </p>
          </div>
        )}

        {/* Section Tabs */}
        {isComplete && (
          <div className="flex gap-1.5 border-b border-slate-200 mb-6 pb-2 overflow-x-auto">
            {[
              { id: "all", label: "All Sections", icon: Layers },
              { id: "verdict", label: "Forensic Verdict", icon: Award },
              { id: "claim", label: "Claim & Assertions", icon: FileText },
              { id: "evidence", label: `Sources (${verdict?.evidence_items?.length || 0})`, icon: Globe },
              { id: "audit", label: `Audit Log (${auditLogs.length})`, icon: History },
            ].map((t) => {
              const Icon = t.icon;
              return (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id as any)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
                    tab === t.id ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  <Icon size={13} /> {t.label}
                </button>
              );
            })}
          </div>
        )}

        {/* Sections */}
        {(tab === "all" || tab === "verdict") && verdict && <VerdictSection verdict={verdict} />}
        {(tab === "all" || tab === "claim") && claim && <ClaimSection claim={claim} />}
        {(tab === "all" || tab === "evidence") && verdict && (
          <EvidenceSection items={verdict.evidence_items} />
        )}
        {(tab === "all" || tab === "audit") && <AuditSection logs={auditLogs} />}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-400">
        DeepVerify Engine — Multi-Modal Narrative &amp; OSINT Authenticity Verification Platform
      </footer>
    </div>
  );
}
