"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getJobs, JobListItem } from "../../../lib/api";
import { DeepVerifyLogo } from "../../components/DeepVerifyLogo";

export default function HistoryPage() {
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getJobs()
      .then(setJobs)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

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
        <div style={{ display: "flex", gap: "16px" }}>
          <Link href="/" style={{ color: "var(--text-muted)", textDecoration: "none", fontWeight: 500, fontSize: "0.9rem" }}>
            New Scan
          </Link>
          <span style={{ color: "var(--indigo-500)", fontWeight: 600, fontSize: "0.9rem" }}>History</span>
        </div>
      </nav>

      <main style={{ maxWidth: "1000px", margin: "0 auto", padding: "40px 24px" }}>
        <h1 style={{ fontSize: "2rem", fontWeight: 800, color: "var(--text-primary)", marginBottom: "8px" }}>
          Recent Scans
        </h1>
        <p style={{ color: "var(--text-muted)", marginBottom: "32px" }}>
          View the history of previously analyzed videos and their authenticity verdicts.
        </p>

        {loading ? (
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="skeleton" style={{ height: "120px", width: "100%", borderRadius: "var(--radius-lg)" }} />
            ))}
          </div>
        ) : error ? (
          <div style={{ padding: "16px", background: "var(--rose-50)", color: "#9f1239", borderRadius: "var(--radius-md)", border: "1px solid var(--rose-100)" }}>
            Failed to load jobs: {error}
          </div>
        ) : jobs.length === 0 ? (
          <div className="card" style={{ padding: "40px", textAlign: "center" }}>
            <p style={{ color: "var(--text-muted)" }}>No jobs found.</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {jobs.map(job => (
              <Link key={job.job_id} href={`/report/${job.job_id}`} style={{ textDecoration: "none" }}>
                <div className="card" style={{
                  padding: "20px", display: "flex", alignItems: "center", justifyContent: "space-between",
                  transition: "all 0.2s ease",
                  cursor: "pointer",
                }}
                onMouseOver={(e) => { e.currentTarget.style.borderColor = "var(--indigo-500)"; e.currentTarget.style.transform = "translateY(-2px)"; }}
                onMouseOut={(e) => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.transform = "none"; }}
                >
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                        {job.job_id.slice(0, 8)}
                      </span>
                      <span style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-primary)" }}>
                        {job.original_filename || (job.source_type === "url" ? "Social Media URL" : "Unknown")}
                      </span>
                    </div>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      {job.created_at ? new Date(job.created_at).toLocaleString() : "Unknown Date"}
                    </span>
                  </div>
                  
                  <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                    <span className={`badge ${
                      job.status === "complete" ? "badge-authentic" :
                      job.status === "failed" ? "badge-deepfake" :
                      "badge-inconclusive"
                    }`}>
                      {job.status.toUpperCase()}
                    </span>
                    <span style={{ color: "var(--text-placeholder)" }}>→</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
