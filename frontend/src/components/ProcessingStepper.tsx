"use client";

import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";

const STAGES = [
  { step: 1, id: "ingesting",  label: "Ingesting Video",         desc: "Downloading or saving uploaded file" },
  { step: 2, id: "c2pa",       label: "C2PA Signature Check",    desc: "Verifying cryptographic content credentials" },
  { step: 3, id: "audio",      label: "Audio Transcription",     desc: "Groq Whisper extracting timestamped transcript" },
  { step: 4, id: "vision",     label: "Facial Artifact Analysis",desc: "MTCNN + EfficientNet deepfake scoring" },
  { step: 5, id: "osint",      label: "OSINT Reverse Search",    desc: "Google Lens searching scene keyframes" },
  { step: 6, id: "synthesis",  label: "LLM Evidence Synthesis",  desc: "GPT-4o-mini composing forensic verdict" },
];

type StageStatus = "pending" | "ingesting" | "c2pa" | "audio" | "vision" | "osint" | "synthesis" | "complete" | "failed";

interface ProcessingStepperProps {
  status: StageStatus;
  currentStep: number;
  errorMessage?: string | null;
}

export function ProcessingStepper({ status, currentStep, errorMessage }: ProcessingStepperProps) {
  const isFailed = status === "failed";
  const isComplete = status === "complete";

  return (
    <div style={{ width: "100%", maxWidth: "560px", margin: "0 auto" }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: "32px" }}>
        {isComplete ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px" }}>
            <div style={{
              width: "56px", height: "56px", borderRadius: "50%",
              background: "var(--emerald-50)", border: "2px solid var(--emerald-100)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <CheckCircle2 size={28} color="var(--emerald-500)" />
            </div>
            <p style={{ fontWeight: 700, fontSize: "1.1rem", color: "var(--text-primary)", margin: 0 }}>
              Analysis Complete
            </p>
          </div>
        ) : isFailed ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px" }}>
            <XCircle size={40} color="var(--rose-500)" />
            <p style={{ fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>Analysis Failed</p>
            {errorMessage && (
              <p style={{ fontSize: "0.85rem", color: "var(--rose-500)", maxWidth: "400px" }}>{errorMessage}</p>
            )}
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px" }}>
            <div style={{ position: "relative", width: "48px", height: "48px" }}>
              <div style={{
                position: "absolute", inset: 0, borderRadius: "50%",
                border: "3px solid var(--indigo-100)",
              }} />
              <div style={{
                position: "absolute", inset: 0, borderRadius: "50%",
                border: "3px solid transparent",
                borderTopColor: "var(--indigo-600)",
                animation: "spin-slow 1s linear infinite",
              }} />
              <div style={{
                position: "absolute", inset: "10px", borderRadius: "50%",
                background: "var(--indigo-50)", display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--indigo-600)" }}>
                  {currentStep}/6
                </span>
              </div>
            </div>
            <p style={{ fontWeight: 600, color: "var(--text-primary)", margin: 0, fontSize: "0.95rem" }}>
              Analyzing your video...
            </p>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", margin: 0 }}>
              This may take 30–120 seconds depending on video length
            </p>
          </div>
        )}
      </div>

      {/* Progress bar */}
      {!isFailed && (
        <div className="progress-track" style={{ marginBottom: "28px" }}>
          <div
            className="progress-fill"
            style={{ width: `${isComplete ? 100 : (currentStep / 6) * 100}%` }}
          />
        </div>
      )}

      {/* Stages */}
      <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
        {STAGES.map((stage, idx) => {
          const stepComplete = currentStep > stage.step || isComplete;
          const stepActive = currentStep === stage.step && !isFailed && !isComplete;
          const stepFailed = isFailed && currentStep === stage.step;
          const stepPending = currentStep < stage.step && !isComplete;

          return (
            <div
              key={stage.id}
              className="animate-fade-in-up"
              style={{
                display: "flex", alignItems: "center", gap: "14px",
                padding: "12px 16px", borderRadius: "var(--radius-md)",
                background: stepActive ? "var(--indigo-50)" : "transparent",
                border: stepActive ? "1px solid var(--indigo-100)" : "1px solid transparent",
                animationDelay: `${idx * 0.05}s`,
                transition: "all 0.2s ease",
              }}
            >
              {/* Icon */}
              <div style={{ flexShrink: 0 }}>
                {stepComplete ? (
                  <CheckCircle2 size={20} color="var(--emerald-500)" />
                ) : stepFailed ? (
                  <XCircle size={20} color="var(--rose-500)" />
                ) : stepActive ? (
                  <Loader2 size={20} color="var(--indigo-600)"
                    style={{ animation: "spin-slow 1s linear infinite" }} />
                ) : (
                  <Circle size={20} color="var(--border-strong)" />
                )}
              </div>

              {/* Text */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{
                  margin: 0, fontWeight: stepActive || stepComplete ? 600 : 400,
                  fontSize: "0.9rem",
                  color: stepPending ? "var(--text-muted)" : stepFailed ? "var(--rose-500)" : "var(--text-primary)",
                }}>
                  {stage.label}
                </p>
                {stepActive && (
                  <p style={{ margin: "2px 0 0", fontSize: "0.775rem", color: "var(--indigo-600)" }}>
                    {stage.desc}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
