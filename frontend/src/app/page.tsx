"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { DeepVerifyLogo } from "../components/DeepVerifyLogo";
import { UploadZone } from "../components/UploadZone";
import { ProcessingStepper } from "../components/ProcessingStepper";
import { analyzeFile, analyzeUrl, getStatus } from "../../lib/api";
import type { StatusResponse } from "../../lib/api";

type AppState = "idle" | "loading" | "polling" | "done" | "failed";

export default function HomePage() {
  const router = useRouter();
  const [appState, setAppState] = useState<AppState>("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [submitError, setSubmitError] = useState("");
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const startPolling = useCallback((id: string) => {
    pollingRef.current = setInterval(async () => {
      try {
        const s = await getStatus(id);
        setStatus(s);
        if (s.status === "complete") {
          stopPolling();
          setAppState("done");
          router.push(`/report/${id}`);
        } else if (s.status === "failed") {
          stopPolling();
          setAppState("failed");
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 2000);
  }, [router, stopPolling]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const handleSubmit = useCallback(async (payload: { file?: File; url?: string }) => {
    setSubmitError("");
    setAppState("loading");

    try {
      const resp = payload.file
        ? await analyzeFile(payload.file)
        : await analyzeUrl(payload.url!);

      setJobId(resp.job_id);
      setAppState("polling");
      startPolling(resp.job_id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Submission failed. Please try again.";
      setSubmitError(msg);
      setAppState("idle");
    }
  }, [startPolling]);

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-base)" }}>
      {/* Nav */}
      <nav style={{
        position: "sticky", top: 0, zIndex: 10,
        background: "rgba(255, 255, 255, 0.85)", backdropFilter: "blur(12px)",
        borderBottom: "1px solid var(--border)",
        padding: "0 32px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        height: "60px",
      }}>
        <DeepVerifyLogo />
        <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
          <a href="/history" style={{ color: "var(--text-muted)", textDecoration: "none", fontWeight: 500, fontSize: "0.9rem" }}>
            History
          </a>
          <div style={{ display: "flex", gap: "8px" }}>
            {["C2PA", "Computer Vision", "Groq Whisper", "OSINT", "LLM Synthesis"].map((tag) => (
              <span key={tag} style={{
                padding: "3px 10px", borderRadius: "999px", fontSize: "0.72rem",
                background: "var(--bg-subtle)", border: "1px solid var(--border)",
                color: "var(--text-muted)", fontWeight: 500,
                display: "none",
              }}
              className="lg-flex"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section style={{
        maxWidth: "900px", margin: "0 auto",
        padding: "80px 24px 40px",
        textAlign: "center",
      }}>
        {/* Badge */}
        <div className="hero-badge-container">
          <span className="hero-badge-dot" />
          <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--indigo-600)" }}>
            Multi-Modal Forensic Engine
          </span>
        </div>

        <h1 style={{
          fontSize: "clamp(2rem, 5vw, 3.2rem)",
          fontWeight: 900,
          color: "var(--text-primary)",
          lineHeight: 1.15,
          margin: "0 0 20px",
          letterSpacing: "-0.02em",
        }}>
          Is this video{" "}
          <span className="hero-gradient-text">real</span>?
        </h1>

        <p style={{
          fontSize: "1.1rem", color: "var(--text-muted)",
          maxWidth: "560px", margin: "0 auto 48px",
          lineHeight: 1.7,
        }}>
          Upload a video or paste a social media link. Our engine checks C2PA credentials,
          facial artifacts, audio consistency, and cross-references the web to produce a
          forensic authenticity verdict.
        </p>

        {/* Feature pills */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", justifyContent: "center", marginBottom: "48px" }}>
          {[
            { icon: "🔐", label: "C2PA Cryptographic Verification" },
            { icon: "👁️", label: "EfficientNet + Grad-CAM" },
            { icon: "🎙️", label: "Groq Whisper Transcription" },
            { icon: "🔍", label: "Google Lens Reverse Search" },
            { icon: "🤖", label: "GPT-4o-mini Synthesis" },
          ].map(({ icon, label }) => (
            <div key={label} className="hero-feature-pill">
              <span className="hero-feature-pill-icon">{icon}</span>
              <span>{label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Main card */}
      <section style={{
        maxWidth: "760px", margin: "0 auto",
        padding: "0 24px 80px",
      }}>
        <div className="hero-main-card">
          {(appState === "idle" || appState === "loading") && (
            <>
              <UploadZone onSubmit={handleSubmit} isLoading={appState === "loading"} />
              {submitError && (
                <div style={{
                  marginTop: "16px", padding: "12px 16px",
                  background: "var(--rose-50)", border: "1px solid var(--rose-100)",
                  borderRadius: "var(--radius-md)", color: "#9f1239",
                  fontSize: "0.85rem",
                }}>
                  ❌ {submitError}
                </div>
              )}
            </>
          )}

          {appState === "polling" && status && (
            <ProcessingStepper
              status={status.status}
              currentStep={status.stage_step}
            />
          )}

          {appState === "failed" && status && (
            <ProcessingStepper
              status="failed"
              currentStep={status.stage_step}
              errorMessage={status.error_message}
              onReset={() => {
                setAppState("idle");
                setJobId(null);
                setStatus(null);
                setSubmitError("");
              }}
            />
          )}

          {appState === "done" && (
            <div style={{ textAlign: "center", padding: "20px" }}>
              <div style={{ fontSize: "3rem", marginBottom: "12px" }}>✅</div>
              <p style={{ fontWeight: 700, color: "var(--text-primary)" }}>
                Redirecting to your forensic report...
              </p>
            </div>
          )}

          {/* Reset button when failed */}
          {appState === "failed" && (
            <div style={{ textAlign: "center", marginTop: "24px" }}>
              <button
                onClick={() => { setAppState("idle"); setJobId(null); setStatus(null); }}
                style={{
                  padding: "10px 24px", borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border)", background: "var(--bg-base)",
                  cursor: "pointer", fontSize: "0.875rem", fontWeight: 600,
                  color: "var(--text-secondary)", fontFamily: "Inter, sans-serif",
                }}
              >
                Try Again
              </button>
            </div>
          )}
        </div>

        {/* How it works */}
        {appState === "idle" && (
          <div style={{ marginTop: "40px" }}>
            <h2 style={{
              textAlign: "center", fontSize: "1.1rem",
              fontWeight: 700, color: "var(--text-primary)", marginBottom: "24px",
            }}>
              6-Stage Forensic Pipeline
            </h2>
            <div style={{
              display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "12px",
            }}>
              {[
                { n: "01", title: "Ingest", desc: "Download via yt-dlp or save upload", color: "var(--indigo-50)", border: "var(--indigo-100)" },
                { n: "02", title: "C2PA", desc: "Verify cryptographic Content Credentials", color: "var(--emerald-50)", border: "var(--emerald-100)" },
                { n: "03", title: "Audio", desc: "Groq Whisper timestamped transcript", color: "var(--violet-50)", border: "var(--violet-100)" },
                { n: "04", title: "Vision", desc: "MTCNN + EfficientNet + Grad-CAM heatmaps", color: "var(--amber-50)", border: "var(--amber-100)" },
                { n: "05", title: "OSINT", desc: "Google Lens scene keyframe search", color: "var(--rose-50)", border: "var(--rose-100)" },
                { n: "06", title: "Verdict", desc: "GPT-4o-mini synthesizes forensic report", color: "var(--indigo-50)", border: "var(--indigo-100)" },
              ].map(({ n, title, desc, color, border }) => (
                <div key={n} className="topic-card" style={{
                  padding: "16px", borderRadius: "var(--radius-lg)",
                  background: color, border: `1px solid ${border}`,
                }}>
                  <span style={{
                    display: "inline-block", fontSize: "0.7rem", fontWeight: 800,
                    color: "var(--text-muted)", marginBottom: "6px",
                    fontFamily: "JetBrains Mono, monospace",
                  }}>
                    {n}
                  </span>
                  <p className="topic-title" style={{ margin: 0, fontWeight: 700, fontSize: "0.9rem", color: "var(--text-primary)", transition: "color 0.2s" }}>
                    {title}
                  </p>
                  <p style={{ margin: "4px 0 0", fontSize: "0.78rem", color: "var(--text-muted)" }}>
                    {desc}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
