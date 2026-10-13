"use client";

import { useState } from "react";
import Link from "next/link";
import { api, type Feedback } from "@/lib/investigation-api";
import styles from "@/components/InvestigationWorkspace.module.css";

type ReviewItem = Feedback & {
  assertion_text: string; content_snippet: string; source_url: string; reviewer: string; fixture: number; predicted_stance: string;
  passage_kind: string; classification_method: string; stance_explanation: string;
  context: string | null; extraction_status: string | null; extraction_error: string | null;
};
type History = { id: string; feedback_id: string; decision: string; reason: string; created_at: string };

export default function ReviewDesk() {
  const [token, setToken] = useState("");
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [history, setHistory] = useState<History[]>([]);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() {
    const data = await api<{ feedback: ReviewItem[]; review_history: History[] }>("/admin/feedback", "GET", undefined, token);
    setItems(data.feedback); setHistory(data.review_history);
  }
  async function act(work: () => Promise<void>) {
    setBusy(true); setError("");
    try { await work(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <div className={styles.workspace}><header className={styles.header}><Link className={styles.brand} href="/">DeepVerify</Link><Link href="/evaluation">Evaluation reports</Link><span>Administrator review desk</span></header>
    <main style={{ maxWidth: 900, margin: "auto", padding: 32 }}>
      <h1>Reviewed feedback</h1><p>Review the assertion and source before approving. Only approved live relevance labels are eligible for ranking training. Stance review updates the assessment separately.</p><p>Automation proposes only unrelated or needing review. Supporting or contradicting stances require your explicit approval after inspecting the source. A supported assessment records reviewed source support, not independent proof; citation support is a separate human evaluation.</p>
      <section className={styles.panel}><label>Administrator token<input type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} /></label>
        <p className={styles.hint}>Token remains in page memory only. This local administration scheme has one shared administrator identity and no account-level roles. Use a trusted local connection.</p>
        <button disabled={busy} onClick={() => act(load)}>Load review queue & history</button></section>
      {error && <p role="alert" className={styles.error}>{error}</p>}
      <label>Review reason (required for each decision)<textarea value={reason} onChange={e => setReason(e.target.value)} minLength={5} maxLength={1000} /></label>
      {items.map(item => <article className={styles.panel} key={item.id}><span className={styles.eyebrow}>{item.fixture ? "OFFLINE FIXTURE · excluded from training" : "LIVE EVIDENCE"}</span>
        <h2>{item.assertion_text}</h2><blockquote>{item.content_snippet}</blockquote><a href={item.source_url} target="_blank" rel="noopener noreferrer">Inspect source ↗</a>
        <p className={styles.hint}>{item.passage_kind} · Extraction: {item.extraction_status || "Legacy evidence — no extraction recorded"}</p>
        {item.context && <details><summary>Stored surrounding context</summary><blockquote>{item.context}</blockquote></details>}
        {item.extraction_error && <p className={styles.warning}>{item.extraction_error}</p>}
        <p className={styles.hint}>{item.classification_method}: {item.stance_explanation}</p>
        <p>Prediction: {item.predicted_stance}<br />Proposed {item.dimension}: <strong>{item.label}</strong> · {item.approval}<br />Session: {item.reviewer}</p>
        <div className={styles.row}>{["approved", "rejected"].map(decision => <button key={decision} disabled={busy || reason.trim().length < 5} onClick={() => act(async () => {
          await api(`/admin/feedback/${item.id}/review`, "POST", { decision, reason }, token); setReason(""); await load();
        })}>{decision === "approved" ? "Approve" : "Reject"}</button>)}</div>
      </article>)}
      <details className={styles.audit}><summary>Preserved review history ({history.length})</summary>{history.map(item => <div key={item.id}>{item.feedback_id}: {item.decision} — {item.reason}<br />{item.created_at}</div>)}</details>
    </main></div>;
}
