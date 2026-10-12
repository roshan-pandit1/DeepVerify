"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type Investigation, type Learning, type Summary, type Evidence } from "@/lib/investigation-api";
import styles from "./InvestigationWorkspace.module.css";

function labels(value: string) { return (JSON.parse(value) as string[]).join(", ") || "Not detected"; }
function date(value: string) { return new Date(value).toLocaleString(); }

export default function InvestigationWorkspace() {
  const [text, setText] = useState("");
  const [inputType, setInputType] = useState("text");
  const [provider, setProvider] = useState("serpapi");
  const [current, setCurrent] = useState<Investigation | null>(null);
  const [edits, setEdits] = useState<string[]>([]);
  const [history, setHistory] = useState<Summary[]>([]);
  const [learning, setLearning] = useState<Learning | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    const [items, status] = await Promise.all([api<Summary[]>("/investigations"), api<Learning>("/learning")]);
    setHistory(items); setLearning(status);
  }, []);

  const load = useCallback(async (id: string) => {
    const item = await api<Investigation>(`/investigations/${id}`);
    setCurrent(item); setEdits(item.assertions.map(a => a.assertion_text));
    window.history.replaceState(null, "", `?investigation=${id}`);
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api<Summary[]>("/investigations"), api<Learning>("/learning")]).then(([items, status]) => {
      if (!cancelled) { setHistory(items); setLearning(status); }
    }).catch(e => { if (!cancelled) setError(`API unavailable. Check NEXT_PUBLIC_API_BASE_URL and start the API. ${e.message}`); });
    const id = new URLSearchParams(window.location.search).get("investigation");
    if (id) api<Investigation>(`/investigations/${id}`).then(item => {
      if (!cancelled) { setCurrent(item); setEdits(item.assertions.map(a => a.assertion_text)); }
    }).catch(e => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!current || !["queued", "retrieving"].includes(current.stage)) return;
    let cancelled = false;
    const timer = setInterval(async () => {
      try {
        const next = await api<Investigation>(`/investigations/${current.claim_id}`);
        if (!cancelled) { setCurrent(next); if (!["queued", "retrieving"].includes(next.stage)) await refresh(); }
      } catch (e) { if (!cancelled) setError(`Progress unavailable; retry opening this investigation. ${(e as Error).message}`); }
    }, 2000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [current, refresh]);

  async function act(work: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await work(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function submitFeedback(evidence: Evidence, dimension: string, label: string) {
    let reviewer = localStorage.getItem("deepverify-reviewer");
    if (!reviewer) { reviewer = crypto.randomUUID(); localStorage.setItem("deepverify-reviewer", reviewer); }
    await api(`/evidence/${evidence.id}/feedback`, "POST", { reviewer, dimension, label });
    if (current) await load(current.claim_id);
    setNotice("Feedback saved for administrator review. Predictions and training data are unchanged until approval.");
  }

  return <div className={styles.workspace}>
    <header className={styles.header}><Link href="/" className={styles.brand}>DeepVerify <span>INVESTIGATIONS</span></Link><nav className={styles.row}><Link href="/review">Review desk</Link><Link href="/evaluation">Evaluation</Link></nav></header>
    <main className={styles.grid}>
      <aside className={styles.sidebar}>
        <section><h2>Research memory</h2><p>Previous investigations, with their evidence and uncertainties.</p>
          <button className={styles.secondary} onClick={() => { setCurrent(null); setNotice(""); window.history.replaceState(null, "", "/"); }}>New investigation</button>
          <div className={styles.history}>{history.map(item => <button key={item.claim_id} className={current?.claim_id === item.claim_id ? styles.selected : ""} onClick={() => act(() => load(item.claim_id))}>
            <strong>{item.memory_text.slice(0, 95)}</strong><small>{item.stage} · {item.provider === "offline" ? "OFFLINE FIXTURE" : "live provider"}<br />{date(item.created_at)}</small>
          </button>)}</div>{history.length === 0 && <p>No investigations yet.</p>}</section>
        <section className={styles.learning}><h2>Learning status</h2><strong>{learning?.status || "Loading status…"}</strong>
          {learning && <><p>{learning.approved_live_examples} approved live relevance labels</p><p>Ranker: {learning.effective_ranker}</p><p>Memory: {learning.memory}</p><p>{learning.training}</p></>}
        </section>
      </aside>
      <div className={styles.content}>
        <div className={styles.intro}><span className={styles.eyebrow}>EVIDENCE FIRST</span><h1>Investigate the claim.<br />Inspect the evidence.</h1><p>Separate what sources support, what they contradict, and what remains unknown.</p></div>
        {error && <div role="alert" className={styles.error}>{error}</div>}
        {notice && <div role="status" className={styles.notice}>{notice}</div>}
        <form className={styles.panel} onSubmit={event => { event.preventDefault(); act(async () => {
          const item = await api<Investigation>("/investigations", "POST", { text, input_type: inputType, provider });
          await load(item.claim_id); await refresh();
        }); }}>
          <h2>Start an investigation</h2><div className={styles.row}>
            <label>Input<select value={inputType} onChange={e => setInputType(e.target.value)}><option value="text">Claim text</option><option value="url">Public article URL</option></select></label>
            <label>Evidence provider<select value={provider} onChange={e => setProvider(e.target.value)}><option value="serpapi">Live search · SerpAPI</option><option value="offline">OFFLINE FIXTURES · development only</option></select></label>
          </div><label htmlFor="claim">{inputType === "text" ? "Factual claim or short excerpt" : "Public HTTP/HTTPS article URL"}</label>
          <textarea id="claim" value={text} onChange={e => setText(e.target.value)} required minLength={5} maxLength={12000} rows={4} placeholder="What would you like to investigate?" />
          <p className={styles.hint}>Up to 12,000 characters. Extraction produces editable candidates; review compound claims and entity details.</p>
          {provider === "offline" && <p className={styles.warning}>Synthetic development evidence only. This mode does not investigate real-world truth.</p>}
          <button disabled={busy} type="submit">{busy ? "Working…" : "Extract assertions →"}</button>
        </form>
        {current && <section className={styles.panel} aria-label="Investigation report">
          <div className={styles.row}><h2>Your investigation</h2><span className={styles.badge}>{current.stage}</span></div>
          <p className={styles.hint}>ID: {current.claim_id} · {current.provider} · {current.job ? `${current.job.attempts} worker attempt(s)` : "Not yet queued"}</p>
          {current.provider === "offline" && <p className={styles.warning}>OFFLINE FIXTURE REPORT — synthetic evidence, no real-world accuracy claim.</p>}
          {current.error && <div className={styles.error}>{current.error}</div>}
          {["queued", "retrieving"].includes(current.stage) && <p role="status">{current.stage === "queued" ? "Waiting for the separate worker. If this persists, start python -m investigation.worker." : "Retrieving evidence. Completed assertions appear below."} {current.searches.filter(s => s.state === "complete").length}/{current.assertions.length} searches completed.</p>}
          {current.stage === "draft" ? <>
            <p>Review each assertion before searching. Split compound statements; include relevant dates and locations. Entity extraction is heuristic.</p>
            {edits.map((value, i) => <div key={i} className={styles.editor}><label htmlFor={`assertion-${i}`}>Assertion {i + 1}</label><textarea id={`assertion-${i}`} value={value} minLength={5} maxLength={1500} onChange={e => setEdits(edits.map((s, n) => n === i ? e.target.value : s))} />
              <button className={styles.secondary} disabled={edits.length === 1} onClick={() => setEdits(edits.filter((_, n) => n !== i))}>Remove</button></div>)}
            <div className={styles.row}><button className={styles.secondary} disabled={edits.length >= 20} onClick={() => setEdits([...edits, ""])}>Add assertion</button>
              <button disabled={busy || edits.some(x => x.trim().length < 5)} onClick={() => act(async () => {
                await api(`/investigations/${current.claim_id}/assertions`, "PUT", { assertions: edits });
                await api(`/investigations/${current.claim_id}/run`, "POST"); await load(current.claim_id); await refresh();
              })}>Save assertions & retrieve evidence</button></div>
          </> : current.assertions.map((assertion, i) => <article key={assertion.id} className={styles.assertion}>
            <span className={styles.eyebrow}>ASSERTION {i + 1}</span><h3>{assertion.assertion_text}</h3>
            <p className={styles.hint}>Entities: {labels(assertion.entity_names_json)} · Dates: {labels(assertion.dates)} · Locations: {labels(assertion.locations)}</p>
            <strong className={styles.badge}>{assertion.assessment}</strong><p>{assertion.explanation}</p>
            {assertion.evidence.length === 0 && <p>No evidence retrieved for this assertion.</p>}
            {assertion.evidence.map(evidence => <div className={styles.evidence} key={evidence.id}>
              <span className={styles.eyebrow}>{evidence.fixture ? "OFFLINE FIXTURE" : evidence.passage_kind}</span>
              <h4><a href={evidence.source_url} target="_blank" rel="noopener noreferrer">{evidence.source_name} ↗</a></h4><p className={styles.url}>{evidence.source_url}</p>
              <blockquote>{evidence.content_snippet}</blockquote>
              {evidence.source && <>
                {evidence.source.context && <details><summary>Surrounding source context</summary><blockquote>{evidence.source.context}</blockquote></details>}
                <p className={styles.hint}>Extraction: {evidence.source.extraction_status} · {evidence.source.extraction_method}<br />
                  Source fetched: {date(evidence.source.source_retrieved_at)} · Date metadata: {evidence.source.date_method || "Unavailable"}</p>
                {evidence.source.extraction_error && <p className={styles.warning}>{evidence.source.extraction_error} This evidence remains a labeled snippet fallback.</p>}
                {evidence.source.extraction_status === "extracted" && <>
                  <a href={evidence.source.final_url} target="_blank" rel="noopener noreferrer">Final article URL ↗</a>
                  <details className={styles.audit}><summary>Passage provenance & original search snippet</summary>
                    <p className={styles.hint}>Source ID: {evidence.source.source_id}<br />Text SHA-256: {evidence.source.content_hash}<br />Response SHA-256: {evidence.source.body_hash}<br />
                      Character offsets: {evidence.source.start_offset}–{evidence.source.end_offset} · {evidence.source.selection_method}</p>
                    <blockquote>{evidence.source.search_snippet}</blockquote>
                  </details>
                </>}
              </>}
              <p className={styles.hint}>Published: {evidence.publication_date || "Unknown"} · Retrieved: {date(evidence.retrieved_at)}<br />Method: {evidence.retrieval_method} · Ranker: {evidence.ranker}</p>
              <p><strong>Stance: {evidence.effective_stance}</strong><br />Prediction: {evidence.predicted_stance} · {evidence.classification_method}<br />
                Review: {evidence.feedback.some(f => f.dimension === "stance" && f.approval === "approved") ? "Approved stance correction" : "Unreviewed prediction"}</p><p>{evidence.explanation}</p>
              <p className={styles.hint}>{evidence.passage_kind === "extracted article passage" ? "Passage selected from stored article text; inspect surrounding context. Extraction is heuristic and may omit content." : "A search snippet is not a full-source passage."} Ranking reflects relevance, not truth or probability. Source dates are unverified publisher/provider metadata. Sufficiency is assessed separately.</p>
              <div className={styles.row}><span>Does it address the assertion?</span>{["relevant", "irrelevant"].map(label => <button className={styles.secondary} key={label} disabled={busy} onClick={() => act(() => submitFeedback(evidence, "relevance", label))}>{label}</button>)}</div>
              <label>Propose a stance correction<select value="" disabled={busy} onChange={event => { if (event.target.value) act(() => submitFeedback(evidence, "stance", event.target.value)); }}><option value="">Choose a proposed stance…</option>{["supporting", "contradicting", "unrelated", "needing review"].map(s => <option key={s}>{s}</option>)}</select></label>
              {evidence.feedback.map(f => <small className={styles.feedback} key={f.id}>{f.dimension}: {f.label} — {f.approval}</small>)}
            </div>)}
          </article>)}
          {current.stage === "partial" && <button disabled={busy} onClick={() => act(async () => { await api(`/investigations/${current.claim_id}/run`, "POST"); await load(current.claim_id); })}>Retry failed searches</button>}
          <section className={styles.related}><h3>Related previous investigations</h3><p className={styles.hint}>Lexical retrieval, not semantic embeddings. Prior research is linked for inspection; every new investigation fetches fresh evidence. Offline and live memories stay separate.</p>
            {current.related.map(item => <button key={item.claim_id} className={styles.secondary} onClick={() => act(() => load(item.claim_id))}>{item.memory_text.slice(0, 100)} · {date(item.created_at)}</button>)}
            {!current.related.length && <p>No related investigations found.</p>}
          </section>
          <details className={styles.audit}><summary>Search queries, failures & processing audit</summary>
            {current.searches.map(s => <div key={s.id}><strong>{s.query}</strong><p>{s.state} · {s.provider} · {date(s.retrieved_at)}<br />Assertion: {s.assertion_id}</p>{s.error && <p className={styles.error}>{s.error}</p>}</div>)}
            {current.audit.map(a => <div key={a.id}><strong>{a.stage_name}</strong><p>{a.output_summary}<br /><small>{date(a.timestamp)}</small></p></div>)}
          </details>
        </section>}
      </div>
    </main>
  </div>;
}
