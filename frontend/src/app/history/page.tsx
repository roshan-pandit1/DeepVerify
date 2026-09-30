"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Shield, ArrowLeft, FileText, Link2, Calendar, AlertCircle, ArrowRight, RefreshCw } from "lucide-react";
import { getLightShade } from "@/lib/colors";

interface ClaimItem {
  id: string;
  raw_input: string;
  input_type: string;
  status: string;
  created_at: string;
}

export default function HistoryPage() {
  const [claims, setClaims] = useState<ClaimItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = async () => {
    try {
      setLoading(true);
      const res = await fetch("http://localhost:8000/api/v1/claims");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setClaims(await res.json());
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load history.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      {/* Navbar */}
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
              Deep<span className="text-blue-600">Verify</span> / History
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button onClick={fetchHistory} className="btn-secondary text-xs">
              <RefreshCw size={12} /> Refresh
            </button>
            <Link href="/" className="btn-primary text-xs py-1.5 px-3">
              New Scan
            </Link>
          </div>
        </div>
      </nav>

      {/* Main Body */}
      <main className="max-w-6xl mx-auto px-6 py-8 flex-1 w-full">
        <div className="mb-6">
          <h1 className="text-2xl font-black text-slate-900">Verification History</h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Browse previously processed claims, verdicts, and evidence audit trails.
          </p>
        </div>

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-center gap-2 mb-4">
            <AlertCircle size={15} /> {error}
          </div>
        )}

        {loading ? (
          <div className="flex flex-col gap-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-white border border-slate-200 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : claims.length === 0 ? (
          <div className="card-box p-10 text-center">
            <FileText size={32} className="mx-auto text-slate-300 mb-3" />
            <h3 className="text-sm font-bold text-slate-800">No verifications yet</h3>
            <p className="text-xs text-slate-500 mt-1 mb-4">Submit a claim on the home page to start your first verification.</p>
            <Link href="/" className="btn-primary text-xs">Start New Scan</Link>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {claims.map((claim, idx) => {
              const shade = getLightShade(idx);
              const isDone = claim.status === "completed";

              return (
                <Link key={claim.id} href={`/results/${claim.id}`} className="no-underline">
                  <div
                    className="flash-card flex items-center justify-between gap-4"
                    style={{ backgroundColor: shade.bg, borderColor: shade.border }}
                  >
                    <div className="flex items-center gap-3.5 min-w-0">
                      <div
                        className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0 shadow-sm"
                        style={{ backgroundColor: "#ffffff", color: shade.accent }}
                      >
                        {claim.input_type === "url" ? <Link2 size={18} /> : <FileText size={18} />}
                      </div>

                      <div className="min-w-0">
                        <div className="flex items-center gap-2 text-xs mb-1">
                          <span className="font-mono bg-white/80 px-1.5 py-0.5 rounded font-semibold text-slate-600">
                            #{claim.id.slice(0, 8)}
                          </span>
                          <span className="font-bold uppercase tracking-wider text-slate-500">
                            {claim.input_type}
                          </span>
                          <span className="text-slate-400">•</span>
                          <span className="text-slate-500 flex items-center gap-1">
                            <Calendar size={11} /> {new Date(claim.created_at).toLocaleDateString()}
                          </span>
                        </div>
                        <p className="text-sm font-bold text-slate-900 truncate m-0">
                          {claim.raw_input}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <span
                        className={`badge-pill text-xs ${
                          isDone ? "bg-emerald-100 text-emerald-800" : "bg-blue-100 text-blue-800"
                        }`}
                      >
                        {claim.status}
                      </span>
                      <ArrowRight size={14} className="text-slate-400" />
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-400">
        DeepVerify Engine — Multi-Modal Narrative &amp; OSINT Authenticity Verification Platform
      </footer>
    </div>
  );
}
