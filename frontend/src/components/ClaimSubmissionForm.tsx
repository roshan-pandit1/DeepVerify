"use client";

import React, { useState } from "react";
import { Send, Link2, FileText, Sparkles, AlertCircle } from "lucide-react";

interface ClaimSubmissionFormProps {
  onClaimSubmitted: (claimId: string) => void;
}

export const ClaimSubmissionForm: React.FC<ClaimSubmissionFormProps> = ({ onClaimSubmitted }) => {
  const [rawInput, setRawInput] = useState("");
  const [inputType, setInputType] = useState<"text" | "url">("text");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawInput.trim()) {
      setError("Please enter a claim text or URL.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/claims", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_input: rawInput, input_type: inputType }),
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
    <div
      style={{
        backgroundColor: "#ffffff",
        border: "1px solid #e5e7eb",
        borderRadius: 14,
        boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
        width: "100%",
      }}
    >
      {/* Card header */}
      <div
        style={{
          padding: "20px 24px 16px",
          borderBottom: "1px solid #f1f5f9",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <div
          style={{
            width: 38,
            height: 38,
            borderRadius: 9,
            backgroundColor: "#e7f0ff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <Sparkles size={17} color="#0d6efd" />
        </div>
        <div>
          <div style={{ fontSize: "1rem", fontWeight: 700, color: "#0f172a", lineHeight: 1.3 }}>
            Submit Narrative Claim
          </div>
          <div style={{ fontSize: "0.78rem", color: "#64748b", marginTop: 2 }}>
            Extract facts, analyze credibility, and audit OSINT evidence
          </div>
        </div>
      </div>

      {/* Card body */}
      <div style={{ padding: "20px 24px 24px" }}>
        {/* Input type toggle */}
        <div
          className="btn-group w-100 mb-3"
          role="group"
          aria-label="Input type"
        >
          <button
            type="button"
            className={`btn ${inputType === "text" ? "btn-primary" : "btn-outline-secondary"}`}
            style={{ fontSize: "0.85rem", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}
            onClick={() => setInputType("text")}
          >
            <FileText size={14} />
            Text Statement
          </button>
          <button
            type="button"
            className={`btn ${inputType === "url" ? "btn-primary" : "btn-outline-secondary"}`}
            style={{ fontSize: "0.85rem", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}
            onClick={() => setInputType("url")}
          >
            <Link2 size={14} />
            Web URL
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <textarea
            rows={4}
            className="form-control mb-3"
            value={rawInput}
            onChange={(e) => setRawInput(e.target.value)}
            placeholder={
              inputType === "url"
                ? "Paste URL (e.g. https://example.com/news-article)..."
                : "Paste a news headline, social media post, or claim text to investigate..."
            }
            style={{
              resize: "none",
              fontSize: "0.875rem",
              borderColor: "#d1d5db",
              borderRadius: 8,
              lineHeight: 1.6,
              color: "#0f172a",
            }}
          />

          {error && (
            <div
              className="alert alert-danger d-flex align-items-center gap-2 py-2 mb-3"
              role="alert"
              style={{ fontSize: "0.82rem", borderRadius: 8 }}
            >
              <AlertCircle size={14} style={{ flexShrink: 0 }} />
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary w-100 d-flex align-items-center justify-content-center gap-2 fw-semibold"
            style={{ padding: "10px 20px", borderRadius: 8, fontSize: "0.9rem" }}
          >
            {loading ? (
              <>
                <span className="spinner-border spinner-border-sm" role="status" />
                Verifying...
              </>
            ) : (
              <>
                Verify Claim Credentials
                <Send size={14} />
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};
