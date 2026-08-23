"use client";

import { useState, useRef, useCallback } from "react";
import { Upload, Link2, X, Film, AlertCircle } from "lucide-react";

interface UploadZoneProps {
  onSubmit: (payload: { file?: File; url?: string }) => void;
  isLoading: boolean;
}

export function UploadZone({ onSubmit, isLoading }: UploadZoneProps) {
  const [mode, setMode] = useState<"file" | "url">("file");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const MAX_MB = 500;
  const ACCEPTED = ["video/mp4", "video/quicktime", "video/webm", "video/x-matroska"];

  const validateFile = (f: File): string | null => {
    if (!ACCEPTED.includes(f.type) && !f.name.match(/\.(mp4|mov|webm|mkv)$/i)) {
      return "Unsupported format. Please upload MP4, MOV, WebM, or MKV.";
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      return `File too large. Maximum size is ${MAX_MB}MB.`;
    }
    return null;
  };

  const handleFileDrop = useCallback((f: File) => {
    setError("");
    const err = validateFile(f);
    if (err) { setError(err); return; }
    setFile(f);
  }, []);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  };

  const handleDragLeave = () => setDragging(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFileDrop(dropped);
  };

  const handleSubmit = () => {
    setError("");
    if (mode === "file") {
      if (!file) { setError("Please select a video file."); return; }
      onSubmit({ file });
    } else {
      if (!url.trim()) { setError("Please enter a valid URL."); return; }
      let validUrl = url.trim().startsWith("http") ? url.trim() : `https://${url.trim()}`;
      try {
        new URL(validUrl); // validate
      } catch {
        setError("Invalid URL format. Please paste a valid web link.");
        return;
      }
      
      // Prevent massive strings masquerading as URLs from crashing idna encoder
      if (validUrl.length > 500) {
        setError("URL is too long. Please paste a standard video link.");
        return;
      }

      onSubmit({ url: validUrl });
    }
  };

  return (
    <div style={{ width: "100%", maxWidth: "680px", margin: "0 auto" }}>
      {/* Mode tabs */}
      <div style={{
        display: "flex",
        background: "var(--bg-subtle)",
        borderRadius: "var(--radius-lg)",
        padding: "4px",
        marginBottom: "20px",
        gap: "4px",
      }}>
        {(["file", "url"] as const).map((m) => (
          <button
            key={m}
            onClick={() => { setMode(m); setError(""); }}
            style={{
              flex: 1,
              padding: "10px",
              borderRadius: "var(--radius-md)",
              border: "none",
              cursor: "pointer",
              fontFamily: "Inter, sans-serif",
              fontWeight: 600,
              fontSize: "0.875rem",
              transition: "all 0.15s ease",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              background: mode === m ? "var(--bg-base)" : "transparent",
              color: mode === m ? "var(--text-primary)" : "var(--text-muted)",
              boxShadow: mode === m ? "var(--shadow-sm)" : "none",
            }}
          >
            {m === "file" ? <Upload size={16} /> : <Link2 size={16} />}
            {m === "file" ? "Upload File" : "Social Media URL"}
          </button>
        ))}
      </div>

      {/* File drop zone */}
      {mode === "file" ? (
        <div
          className={`upload-zone${dragging ? " drag-active" : ""}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          style={{
            padding: "56px 32px",
            textAlign: "center",
            cursor: "pointer",
            position: "relative",
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm,.mkv"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFileDrop(f);
            }}
          />

          {file ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "12px" }}>
              <div style={{
                width: "56px", height: "56px", borderRadius: "var(--radius-lg)",
                background: "var(--indigo-50)", display: "flex", alignItems: "center",
                justifyContent: "center",
              }}>
                <Film size={28} color="var(--indigo-600)" />
              </div>
              <div>
                <p style={{ fontWeight: 600, color: "var(--text-primary)", margin: 0, fontSize: "0.95rem" }}>
                  {file.name}
                </p>
                <p style={{ color: "var(--text-muted)", margin: "4px 0 0", fontSize: "0.8rem" }}>
                  {(file.size / 1024 / 1024).toFixed(1)} MB
                </p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); setFile(null); }}
                style={{
                  display: "flex", alignItems: "center", gap: "4px", padding: "4px 12px",
                  border: "1px solid var(--border)", borderRadius: "999px", background: "var(--bg-base)",
                  cursor: "pointer", fontSize: "0.78rem", color: "var(--text-muted)",
                  fontFamily: "Inter, sans-serif",
                }}
              >
                <X size={12} /> Remove
              </button>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "16px" }}>
              <div style={{
                width: "72px", height: "72px", borderRadius: "var(--radius-xl)",
                background: "var(--bg-subtle)", border: "2px dashed var(--border-strong)",
                display: "flex", alignItems: "center", justifyContent: "center",
                transition: "all 0.2s ease",
              }}>
                <Upload size={32} color={dragging ? "var(--indigo-600)" : "var(--text-muted)"} />
              </div>
              <div>
                <p style={{ fontWeight: 600, color: "var(--text-primary)", margin: 0, fontSize: "1rem" }}>
                  {dragging ? "Drop your video here" : "Drag & drop your video"}
                </p>
                <p style={{ color: "var(--text-muted)", margin: "6px 0 0", fontSize: "0.85rem" }}>
                  or <span style={{ color: "var(--indigo-600)", fontWeight: 600 }}>click to browse</span>
                  {" "}— MP4, MOV, WebM up to 500MB
                </p>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* URL input */
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ position: "relative" }}>
            <Link2 size={18} color="var(--text-muted)" style={{
              position: "absolute", left: "16px", top: "50%", transform: "translateY(-50%)",
              pointerEvents: "none",
            }} />
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              placeholder="https://youtube.com/watch?v=... or TikTok, X, Reddit"
              style={{
                width: "100%", padding: "14px 16px 14px 46px",
                border: "2px solid var(--border)", borderRadius: "var(--radius-lg)",
                fontSize: "0.95rem", fontFamily: "Inter, sans-serif",
                color: "var(--text-primary)", background: "var(--bg-base)",
                outline: "none", transition: "border-color 0.15s ease",
                boxSizing: "border-box",
              }}
              onFocus={(e) => (e.target.style.borderColor = "var(--indigo-500)")}
              onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
            />
          </div>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {["YouTube", "TikTok", "X / Twitter", "Reddit", "Instagram"].map((p) => (
              <span key={p} style={{
                padding: "2px 10px", borderRadius: "999px", fontSize: "0.75rem",
                background: "var(--bg-subtle)", border: "1px solid var(--border)",
                color: "var(--text-muted)", fontWeight: 500,
              }}>
                {p}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          display: "flex", alignItems: "center", gap: "8px",
          marginTop: "12px", padding: "10px 14px",
          background: "var(--rose-50)", border: "1px solid var(--rose-100)",
          borderRadius: "var(--radius-md)", color: "#9f1239", fontSize: "0.85rem",
        }}>
          <AlertCircle size={16} style={{ flexShrink: 0 }} />
          {error}
        </div>
      )}

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={isLoading}
        style={{
          width: "100%", marginTop: "20px",
          padding: "14px", borderRadius: "var(--radius-lg)",
          border: "none", cursor: isLoading ? "not-allowed" : "pointer",
          background: isLoading ? "var(--bg-muted)" : "linear-gradient(135deg, var(--indigo-600), #38bdf8)",
          color: isLoading ? "var(--text-muted)" : "#ffffff",
          fontFamily: "Inter, sans-serif", fontSize: "1rem", fontWeight: 700,
          letterSpacing: "0.01em", transition: "all 0.2s ease",
          boxShadow: isLoading ? "none" : "0 4px 14px -2px rgba(14,165,233,0.4)",
        }}
        onMouseEnter={(e) => {
          if (!isLoading) (e.target as HTMLButtonElement).style.transform = "translateY(-1px)";
        }}
        onMouseLeave={(e) => {
          (e.target as HTMLButtonElement).style.transform = "translateY(0)";
        }}
      >
        {isLoading ? (
          <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}>
            <span style={{
              width: "18px", height: "18px", border: "2px solid var(--border-strong)",
              borderTopColor: "var(--text-muted)", borderRadius: "50%",
              animation: "spin-slow 0.8s linear infinite", display: "inline-block",
            }} />
            Submitting...
          </span>
        ) : (
          "🔍 Analyze Video"
        )}
      </button>
    </div>
  );
}
