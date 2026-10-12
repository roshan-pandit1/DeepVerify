"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/investigation-api";
import styles from "@/components/InvestigationWorkspace.module.css";

type Metrics = { "precision@5": number; "ndcg@5": number; examples: number; assertions: number };
type Report = {
  report_id: string; dataset_id: string; dataset_version: string; partition: string; synthetic: boolean;
  model_id: string; seed: number; counts: { cases: number; evidence: number; groups: number };
  ranking: { status: string; baseline: Metrics | null; candidate: Metrics | null; promotion_gate_passed: boolean };
  limitations: string[];
};
type EvaluationData = {
  datasets: { id: string; name: string; version: string; state: string; synthetic: number }[];
  reports: Report[];
  promotion_decisions: { id: string; model_id: string; action: string; created_at: string }[];
  legacy_ranking_reports: unknown[];
};

export default function Evaluation() {
  const [token, setToken] = useState("");
  const [data, setData] = useState<EvaluationData | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() {
    setBusy(true); setError("");
    try { setData(await api<EvaluationData>("/admin/evaluations", "GET", undefined, token)); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <div className={styles.workspace}>
    <header className={styles.header}><Link className={styles.brand} href="/">DeepVerify</Link><Link href="/review">Review desk</Link></header>
    <main style={{ maxWidth: 1000, margin: "auto", padding: 32 }}>
      <span className={styles.eyebrow}>MEASURE EACH STAGE</span><h1>Evidence quality & ranking evaluation</h1>
      <p>Relevance ranking, passage stance, extraction, sufficiency, and citation support are evaluated separately. Ranking metrics are not factual confidence scores.</p>
      <section className={styles.panel}><label>Administrator token<input type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} /></label><button disabled={busy} onClick={load}>Load saved evaluation reports</button>
        <p className={styles.hint}>Token remains in page memory. Create, label, freeze, train, and evaluate datasets using the documented administrator CLI. Frozen holdouts are for a single final audit; validation selects models.</p></section>
      {error && <p className={styles.error} role="alert">{error}</p>}
      {data && <>
        <section className={styles.panel}><h2>Reviewable datasets ({data.datasets.length})</h2>
          {data.datasets.map(d => <p key={d.id}><strong>{d.name} · {d.version}</strong> — {d.state} {d.synthetic ? "· SYNTHETIC" : "· review provenance required"}<br /><small>{d.id}</small></p>)}
          {!data.datasets.length && <p>Evaluation pending: no reviewed dataset is available. No demonstrated improvement over the baseline.</p>}
        </section>
        {!data.reports.length && <p>No stage-evaluation reports yet. Synthetic tests do not establish real-world quality.</p>}
        {data.reports.map(r => <article key={r.report_id} className={styles.panel}>
          <span className={styles.eyebrow}>{r.synthetic ? "SYNTHETIC · FUNCTIONALITY ONLY" : "REVIEWED SAMPLE · SEE PROVENANCE"}</span>
          <h2>{r.partition} · dataset {r.dataset_version}</h2><p>{r.counts.cases} assertions · {r.counts.evidence} passages · {r.counts.groups} independent groups · seed {r.seed}</p>
          <p className={styles.hint}>Candidate: {r.model_id}<br />Dataset: {r.dataset_id}</p>
          <h3>Ranking on identical examples</h3><p>{r.ranking.status}</p>
          <div style={{ overflowX: "auto" }}><table className="table"><thead><tr><th>Ranker</th><th>Precision@5</th><th>NDCG@5</th><th>Examples</th></tr></thead><tbody>
            {([ ["Baseline", r.ranking.baseline], ["Candidate", r.ranking.candidate] ] as const).map(([label, m]) => <tr key={label}><th>{label}</th><td>{m ? m["precision@5"].toFixed(3) : "Insufficient data"}</td><td>{m ? m["ndcg@5"].toFixed(3) : "Insufficient data"}</td><td>{m?.examples ?? 0}</td></tr>)}
          </tbody></table></div>
          <p><strong>{r.partition === "holdout" ? "Final audit only — cannot authorize promotion" : r.ranking.promotion_gate_passed ? "Validation ranking gate passed" : "Promotion gate not passed — retain active model"}</strong></p>
          <details className={styles.audit}><summary>Full stage metrics, labels, methods, and limitations</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", fontSize: 12 }}>{JSON.stringify(r, null, 2)}</pre></details>
        </article>)}
        <details className={styles.audit}><summary>Promotion decisions & legacy ranking reports</summary>
          {data.promotion_decisions.map(d => <p key={d.id}>{d.action} · {d.model_id} · {d.created_at}</p>)}
          <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(data.legacy_ranking_reports, null, 2)}</pre>
        </details>
      </>}
    </main>
  </div>;
}
