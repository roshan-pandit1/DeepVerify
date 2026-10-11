"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Shield,
  Sparkles,
  Send,
  FileText,
  Link2,
  AlertCircle,
  History,
  Search,
  Globe,
  ShieldCheck,
} from "lucide-react";
import { getLightShade } from "@/lib/colors";

const SAMPLES = [
  {
    type: "url" as const,
    label: "Instagram Reel",
    val: "https://www.instagram.com/reel/DUNa5h9koyl/?utm_source=ig_web_button_share_sheet",
  },
  {
    type: "text" as const,
    label: "AI Tech Claim",
    val: "OpenAI announced a new quantum-resistant neural architecture for autonomous robotics.",
  },
  {
    type: "text" as const,
    label: "Health Claim",
    val: "WHO confirms drinking green tea prevents 99% of respiratory viral infections in winter.",
  },
];

const FEATURES = [
  { icon: ShieldCheck, title: "Claim Decomposition", desc: "Decomposes statements into atomic verifiable assertions with entity tags." },
  { icon: Search, title: "OSINT Web Crawling", desc: "Cross-references claims across search engines and authoritative repositories." },
  { icon: Globe, title: "Credibility Scoring", desc: "Calculates domain trust scores and classifies stance alignment." },
  { icon: FileText, title: "Audit Trail", desc: "Maintains an immutable forensic log of every pipeline execution stage in ms." },
];

export default function Home() {
  const router = useRouter();
  const [input, setInput] = useState("");
  const [type, setType] = useState<"text" | "url">("text");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return setError("Please enter a claim text or URL.");
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/claims", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_input: input, input_type: type }),
      });
      if (!res.ok) throw new Error((await res.json()).message || "Submission failed.");
      const data = await res.json();
      router.push(`/results/${data.id}`);
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred.");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      {/* Top Navbar */}
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-sm">
              <Shield size={20} />
            </div>
            <div>
              <span className="font-extrabold text-slate-900 text-lg">
                Deep<span className="text-blue-600">Verify</span>
              </span>
              <span className="text-xs text-slate-400 ml-2 font-medium">v2.0</span>
            </div>
          </div>
          <Link href="/history" className="btn-secondary">
            <History size={14} /> Scan History
          </Link>
        </div>
      </nav>

      {/* Hero Header */}
      <header className="bg-gradient-to-b from-blue-50 to-slate-50 border-b border-slate-200 py-10 px-6 text-center">
        <div className="max-w-2xl mx-auto">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-700 mb-3">
            <Sparkles size={13} /> Multi-Modal Fact Verification
          </span>
          <h1 className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight">
            Verify Any Claim in <span className="text-blue-600">Seconds</span>
          </h1>
          <p className="mt-2.5 text-slate-600 text-sm sm:text-base">
            Paste a news headline, social media post, or URL. Our AI pipeline extracts facts,
            cross-references OSINT sources, and returns a verified classification.
          </p>
        </div>
      </header>

      {/* Main Grid */}
      <main className="max-w-6xl mx-auto px-6 py-8 flex-1 grid grid-cols-1 lg:grid-cols-2 gap-8 items-start w-full">
        {/* Left: Input Form Card */}
        <div className="card-box p-6">
          {/* Toggle Type */}
          <div className="flex border border-slate-200 rounded-lg overflow-hidden mb-4">
            {(["text", "url"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => { setType(t); setError(null); }}
                className={`flex-1 py-2 text-sm font-semibold flex items-center justify-center gap-2 transition-colors ${
                  type === t ? "bg-blue-600 text-white" : "bg-slate-50 text-slate-600 hover:bg-slate-100"
                }`}
              >
                {t === "text" ? <><FileText size={15} /> Text Statement</> : <><Link2 size={15} /> Social / Web URL</>}
              </button>
            ))}
          </div>

          {/* Quick Sample Prompts */}
          <div className="mb-4">
            <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Try an example:</span>
            <div className="flex flex-wrap gap-2 mt-1.5">
              {SAMPLES.map((s, i) => {
                const shade = getLightShade(i + 2);
                return (
                  <button
                    key={i}
                    type="button"
                    onClick={() => { setType(s.type); setInput(s.val); setError(null); }}
                    style={{ backgroundColor: shade.bg, borderColor: shade.border, color: shade.text }}
                    className="px-2.5 py-1 rounded text-xs font-medium border hover:opacity-85 transition-opacity"
                  >
                    {s.label}
                  </button>
                );
              })}
            </div>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <textarea
              rows={4}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={type === "url" ? "Paste URL (e.g. https://www.instagram.com/reel/..., YouTube, or news link)..." : "Paste a news statement, viral quote, or claim text..."}
              className="w-full p-3 border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:border-blue-500 resize-none leading-relaxed"
            />
            {error && (
              <div className="flex items-center gap-2 p-2.5 text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg">
                <AlertCircle size={15} className="shrink-0" /> {error}
              </div>
            )}
            <button type="submit" disabled={loading} className="btn-primary w-full py-3">
              {loading ? (
                <><span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" /> Verifying Claim...</>
              ) : (
                <>Verify Claim Credentials <Send size={15} /></>
              )}
            </button>
          </form>
        </div>

        {/* Right: Flash Cards with Random / Light Shade Colors */}
        <div className="flex flex-col gap-3">
          <h2 className="text-lg font-bold text-slate-900 mb-1">Automated Verification Stages</h2>
          {FEATURES.map((f, i) => {
            const shade = getLightShade(i);
            const Icon = f.icon;
            return (
              <div
                key={i}
                className="flash-card flex items-start gap-4"
                style={{ backgroundColor: shade.bg, borderColor: shade.border }}
              >
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0 shadow-sm"
                  style={{ backgroundColor: "#ffffff", color: shade.accent }}
                >
                  <Icon size={18} />
                </div>
                <div>
                  <h3 className="text-sm font-bold" style={{ color: shade.text }}>{f.title}</h3>
                  <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">{f.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-400">
        DeepVerify Engine — Multi-Modal Narrative &amp; OSINT Authenticity Verification Platform
      </footer>
    </div>
  );
}
