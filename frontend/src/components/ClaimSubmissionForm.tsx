"use client";

import React, { useState } from "react";
import { Send, Link2, FileText, Sparkles, AlertCircle } from "lucide-react";

interface ClaimSubmissionFormProps {
  onClaimSubmitted: (claimId: string) => void;
}

export const ClaimSubmissionForm: React.FC<ClaimSubmissionFormProps> = ({ onClaimSubmitted }) => {
  const [rawInput, setRawInput] = useState("");
  const [inputType, setInputType] = useState<"text" | "url" | "media">("text");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawInput.trim()) {
      setError("Please enter a claim text, URL, or media summary.");
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const res = await fetch("http://localhost:8000/api/v1/claims", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          raw_input: rawInput,
          input_type: inputType,
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.message || "Failed to submit claim.");
      }

      const data = await res.json();
      setRawInput("");
      onClaimSubmitted(data.id);
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-2xl p-6 shadow-2xl">
      <div className="flex items-center space-x-3 mb-6">
        <div className="p-2.5 bg-blue-600/20 text-blue-400 rounded-xl border border-blue-500/30">
          <Sparkles className="w-6 h-6" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide">Submit Narrative Claim</h2>
          <p className="text-sm text-slate-400">Extract facts, analyze credibility, and audit OSINT evidence</p>
        </div>
      </div>

      <div className="flex space-x-2 mb-4 bg-slate-950 p-1.5 rounded-xl border border-slate-850">
        <button
          type="button"
          onClick={() => setInputType("text")}
          className={`flex-1 flex items-center justify-center space-x-2 py-2 text-sm font-medium rounded-lg transition-all ${
            inputType === "text" ? "bg-blue-600 text-white shadow-lg" : "text-slate-400 hover:text-white"
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Text Statement</span>
        </button>
        <button
          type="button"
          onClick={() => setInputType("url")}
          className={`flex-1 flex items-center justify-center space-x-2 py-2 text-sm font-medium rounded-lg transition-all ${
            inputType === "url" ? "bg-blue-600 text-white shadow-lg" : "text-slate-400 hover:text-white"
          }`}
        >
          <Link2 className="w-4 h-4" />
          <span>Web URL</span>
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <textarea
            rows={4}
            value={rawInput}
            onChange={(e) => setRawInput(e.target.value)}
            placeholder={
              inputType === "url"
                ? "Paste URL (e.g. https://example.com/news-article)..."
                : "Paste online claim, news headline, or post text to investigate..."
            }
            className="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-sm transition-all"
          />
        </div>

        {error && (
          <div className="flex items-center space-x-2 text-red-400 bg-red-950/40 border border-red-800/50 p-3 rounded-xl text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold py-3 px-6 rounded-xl transition-all shadow-lg flex items-center justify-center space-x-2 disabled:opacity-50"
        >
          {loading ? (
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <>
              <span>Verify Claim Credentials</span>
              <Send className="w-4 h-4" />
            </>
          )}
        </button>
      </form>
    </div>
  );
};
