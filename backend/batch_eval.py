#!/usr/bin/env python3
"""
batch_eval.py — Batch ground-truth evaluation harness for DeepVerify.

Submits N videos concurrently, polls until complete, then scores the
pipeline verdict against provided ground-truth labels.

Outputs:
  - Per-video verdict table
  - Confusion matrix
  - Precision / Recall / F1 per class
  - Per-signal accuracy contribution
"""
import asyncio
import json
import time
import sys
from dataclasses import dataclass
from typing import Optional

import httpx

API_BASE = "http://localhost:8000"
POLL_INTERVAL = 4          # seconds between status polls
JOB_TIMEOUT  = 600         # max seconds to wait per job

# ── ANSI colours ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

# ── Ground-truth dataset ──────────────────────────────────────────────────────
# Verdict category labels must match pipeline output exactly:
#   "Authentic"              → real, unedited content
#   "AI-Generated Deepfake"  → synthetic / generative AI video
#   "Out-of-Context Cheapfake" → real footage misrepresented / reused across accounts

EVAL_DATASET = [
    {
        "url": "https://www.instagram.com/reel/DVywsc8D7Er/?igsi=dG40NXFyM3ZzbGcz",
        "ground_truth": "AI-Generated Deepfake",
        "description": "Completely AI-generated reel",
    },
    {
        "url": "https://www.instagram.com/reel/DbuhsfeSaX7/?utm_source=ig_web_copy_link&igsi=NTc4MTIwNjQ2YQ==",
        "ground_truth": "AI-Generated Deepfake",
        "description": "Completely AI-generated reel",
    },
    {
        "url": "https://www.instagram.com/reel/DcgQha9T4xk/?utm_source=ig_web_copy_link&igsi=NTc4MTIwNjQ2YQ==",
        "ground_truth": "Authentic",
        "description": "Authentic real news footage",
    },
    {
        "url": "https://www.instagram.com/reel/DcX3vMjoL0Q/?igsi=b2U5Nm1zeGd0dXI4",
        "ground_truth": "Out-of-Context Cheapfake",
        "description": "Real video reused by multiple accounts",
    },
    {
        "url": "https://www.instagram.com/reel/Db2yyW_B2H1/?utm_source=ig_web_copy_link&igsi=NTc4MTIwNjQ2YQ==",
        "ground_truth": "Out-of-Context Cheapfake",
        "description": "Real video reused by multiple accounts",
    },
    {
        "url": "https://www.instagram.com/reel/DcflyqIShGI/?utm_source=ig_web_copy_link&igsi=NTc4MTIwNjQ2YQ==",
        "ground_truth": "Authentic",
        "description": "Authentic real video",
    },
]

ALL_CLASSES = ["Authentic", "AI-Generated Deepfake", "Out-of-Context Cheapfake", "Manipulated Audio", "Inconclusive"]


@dataclass
class EvalResult:
    url: str
    description: str
    ground_truth: str
    job_id: Optional[str]
    pipeline_verdict: Optional[str]
    authenticity_score: Optional[int]
    headline: Optional[str]
    temporal_is_manipulated: Optional[bool]
    temporal_mean_score: Optional[float]
    facial_artifact_score: Optional[float]
    signal_anomaly: Optional[bool]
    osint_match_count: int
    error: Optional[str]
    elapsed_s: float
    correct: Optional[bool] = None


# ── API helpers ───────────────────────────────────────────────────────────────

async def submit_job(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        resp = await client.post(
            f"{API_BASE}/api/analyze",
            data={"source_url": url},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["job_id"]
    except Exception as exc:
        print(f"{RED}  [SUBMIT ERROR] {url[:60]}…: {exc}{RESET}")
        return None


async def poll_job(client: httpx.AsyncClient, job_id: str) -> dict:
    """Poll until complete or failed; returns the status dict."""
    deadline = time.time() + JOB_TIMEOUT
    while time.time() < deadline:
        try:
            resp = await client.get(f"{API_BASE}/api/status/{job_id}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data["status"] in ("complete", "failed"):
                    return data
        except Exception:
            pass
        await asyncio.sleep(POLL_INTERVAL)
    return {"status": "timeout", "error_message": f"Timed out after {JOB_TIMEOUT}s"}


async def fetch_report(client: httpx.AsyncClient, job_id: str) -> Optional[dict]:
    try:
        resp = await client.get(f"{API_BASE}/api/report/{job_id}", timeout=20)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


# ── Per-video runner ──────────────────────────────────────────────────────────

async def run_single(
    client: httpx.AsyncClient,
    entry: dict,
    index: int,
) -> EvalResult:
    url   = entry["url"]
    gt    = entry["ground_truth"]
    desc  = entry["description"]

    t0 = time.time()
    label = f"Video {index+1}/{len(EVAL_DATASET)}"
    print(f"{CYAN}  [{label}] Submitting: {url[:70]}…{RESET}")

    job_id = await submit_job(client, url)
    if not job_id:
        return EvalResult(
            url=url, description=desc, ground_truth=gt,
            job_id=None, pipeline_verdict=None, authenticity_score=None,
            headline=None, temporal_is_manipulated=None, temporal_mean_score=None,
            facial_artifact_score=None, signal_anomaly=None, osint_match_count=0,
            error="Submit failed", elapsed_s=time.time() - t0,
        )

    print(f"  [{label}] Job ID: {job_id} — polling…")
    status_data = await poll_job(client, job_id)

    if status_data["status"] != "complete":
        err = status_data.get("error_message") or status_data.get("status")
        print(f"{YELLOW}  [{label}] FAILED: {err}{RESET}")
        return EvalResult(
            url=url, description=desc, ground_truth=gt,
            job_id=job_id, pipeline_verdict=None, authenticity_score=None,
            headline=None, temporal_is_manipulated=None, temporal_mean_score=None,
            facial_artifact_score=None, signal_anomaly=None, osint_match_count=0,
            error=err, elapsed_s=time.time() - t0,
        )

    report = await fetch_report(client, job_id)
    elapsed = time.time() - t0

    if not report:
        return EvalResult(
            url=url, description=desc, ground_truth=gt,
            job_id=job_id, pipeline_verdict=None, authenticity_score=None,
            headline=None, temporal_is_manipulated=None, temporal_mean_score=None,
            facial_artifact_score=None, signal_anomaly=None, osint_match_count=0,
            error="Could not fetch report", elapsed_s=elapsed,
        )

    verdict = report.get("verdict", {})
    temporal = report.get("temporal", {})
    temporal_metrics = temporal.get("metrics", {})
    signal = report.get("signal_forensics", {})
    osint  = report.get("osint", {})

    pipeline_verdict = verdict.get("verdict_category")
    auth_score = verdict.get("authenticity_score")
    correct = (pipeline_verdict == gt)

    icon = GREEN + "✅ CORRECT" + RESET if correct else RED + "❌ WRONG" + RESET
    print(
        f"  [{label}] Done in {elapsed:.0f}s | GT: {BOLD}{gt}{RESET} | "
        f"Pipeline: {BOLD}{pipeline_verdict}{RESET} ({auth_score}%) | {icon}"
    )

    return EvalResult(
        url=url, description=desc, ground_truth=gt,
        job_id=job_id, pipeline_verdict=pipeline_verdict, authenticity_score=auth_score,
        headline=verdict.get("summary_headline"),
        temporal_is_manipulated=temporal.get("is_manipulated"),
        temporal_mean_score=temporal_metrics.get("mean_fake_score"),
        facial_artifact_score=report.get("vision", {}).get("facial_artifact_score"),
        signal_anomaly=signal.get("signal_anomaly_detected"),
        osint_match_count=len(osint.get("matches", [])),
        error=None, elapsed_s=elapsed, correct=correct,
    )


# ── Scoring & reporting ───────────────────────────────────────────────────────

def normalise_verdict(v: Optional[str]) -> str:
    """Collapse 'Inconclusive' into nearest class for scoring."""
    if v is None:
        return "ERROR"
    return v


def compute_metrics(results: list[EvalResult]) -> dict:
    """Compute per-class precision, recall, F1 and overall accuracy."""
    classes = ["Authentic", "AI-Generated Deepfake", "Out-of-Context Cheapfake"]

    # Build confusion matrix counts
    tp = {c: 0 for c in classes}
    fp = {c: 0 for c in classes}
    fn = {c: 0 for c in classes}

    for r in results:
        gt  = r.ground_truth
        pred = normalise_verdict(r.pipeline_verdict)
        for c in classes:
            if gt == c and pred == c:
                tp[c] += 1
            elif pred == c and gt != c:
                fp[c] += 1
            elif gt == c and pred != c:
                fn[c] += 1

    metrics = {}
    for c in classes:
        prec = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) > 0 else 0.0
        rec  = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) > 0 else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        metrics[c] = {"precision": prec, "recall": rec, "f1": f1, "tp": tp[c], "fp": fp[c], "fn": fn[c]}

    total_valid = sum(1 for r in results if r.correct is not None)
    total_correct = sum(1 for r in results if r.correct)
    metrics["__overall__"] = {
        "accuracy": total_correct / total_valid if total_valid else 0.0,
        "correct": total_correct,
        "total": total_valid,
    }
    return metrics


def print_report(results: list[EvalResult], metrics: dict):
    sep = "=" * 100

    print(f"\n{BOLD}{sep}{RESET}")
    print(f"{BOLD}  DEEPVERIFY BATCH EVALUATION REPORT{RESET}")
    print(f"{BOLD}{sep}{RESET}\n")

    # ── Per-video table ───────────────────────────────────────────────────
    print(f"{BOLD}{'#':<3} {'Ground Truth':<28} {'Pipeline Verdict':<28} {'Score':>5} {'Status':<12} {'Time':>6}  Description{RESET}")
    print("-" * 100)

    for i, r in enumerate(results):
        icon = "✅" if r.correct else ("❌" if r.correct is False else "⚠️ ")
        score_str = f"{r.authenticity_score}%" if r.authenticity_score is not None else "N/A"
        pred_str  = r.pipeline_verdict or r.error or "ERROR"
        elapsed   = f"{r.elapsed_s:.0f}s"
        print(
            f"{i+1:<3} {r.ground_truth:<28} {pred_str:<28} {score_str:>5}  {icon}          {elapsed:>5}  {r.description}"
        )

    print()

    # ── Signal contribution table ─────────────────────────────────────────
    print(f"{BOLD}{'#':<3} {'Temporal':>10} {'FacialArt%':>11} {'SignalAnom':>11} {'OSINT Matches':>14}{RESET}")
    print("-" * 55)
    for i, r in enumerate(results):
        t_score = f"{r.temporal_mean_score:.3f}" if r.temporal_mean_score is not None else "N/A"
        fa      = f"{r.facial_artifact_score:.1f}%" if r.facial_artifact_score is not None else "N/A"
        sa      = "YES" if r.signal_anomaly else ("NO" if r.signal_anomaly is not None else "N/A")
        print(f"{i+1:<3} {t_score:>10} {fa:>11} {sa:>11} {r.osint_match_count:>14}")

    print()

    # ── Class-level metrics ───────────────────────────────────────────────
    print(f"{BOLD}{'CLASS':<30} {'Precision':>10} {'Recall':>10} {'F1':>10} {'TP':>4} {'FP':>4} {'FN':>4}{RESET}")
    print("-" * 75)
    for cls in ["Authentic", "AI-Generated Deepfake", "Out-of-Context Cheapfake"]:
        m = metrics.get(cls, {})
        prec = f"{m.get('precision', 0):.2f}"
        rec  = f"{m.get('recall', 0):.2f}"
        f1   = f"{m.get('f1', 0):.2f}"
        tp   = m.get("tp", 0)
        fp   = m.get("fp", 0)
        fn   = m.get("fn", 0)
        print(f"{cls:<30} {prec:>10} {rec:>10} {f1:>10} {tp:>4} {fp:>4} {fn:>4}")

    overall = metrics.get("__overall__", {})
    acc = overall.get("accuracy", 0.0)
    correct = overall.get("correct", 0)
    total   = overall.get("total", 0)
    acc_color = GREEN if acc >= 0.8 else (YELLOW if acc >= 0.5 else RED)
    print()
    print(f"{BOLD}Overall Accuracy: {acc_color}{acc:.1%}{RESET}{BOLD}  ({correct}/{total} videos correct){RESET}")

    # ── Misclassified videos ──────────────────────────────────────────────
    wrong = [r for r in results if r.correct is False]
    if wrong:
        print(f"\n{BOLD}{YELLOW}Misclassified Videos:{RESET}")
        for r in wrong:
            print(f"  • {r.description}")
            print(f"    GT={r.ground_truth}  →  Predicted={r.pipeline_verdict}  (score={r.authenticity_score}%)")
            print(f"    Temporal={r.temporal_mean_score}, Facial={r.facial_artifact_score}%, SignalAnom={r.signal_anomaly}")
            print(f"    Headline: {r.headline}")
            print(f"    URL: {r.url}")

    print(f"\n{BOLD}{sep}{RESET}\n")

    # ── Save JSON report ─────────────────────────────────────────────────
    report_dict = {
        "summary": {
            "accuracy": overall.get("accuracy"),
            "correct": correct,
            "total": total,
        },
        "per_class_metrics": {
            cls: metrics[cls]
            for cls in ["Authentic", "AI-Generated Deepfake", "Out-of-Context Cheapfake"]
            if cls in metrics
        },
        "videos": [
            {
                "url": r.url,
                "description": r.description,
                "ground_truth": r.ground_truth,
                "pipeline_verdict": r.pipeline_verdict,
                "authenticity_score": r.authenticity_score,
                "correct": r.correct,
                "headline": r.headline,
                "job_id": r.job_id,
                "elapsed_s": round(r.elapsed_s, 1),
                "signals": {
                    "temporal_mean_score": r.temporal_mean_score,
                    "temporal_is_manipulated": r.temporal_is_manipulated,
                    "facial_artifact_score": r.facial_artifact_score,
                    "signal_anomaly": r.signal_anomaly,
                    "osint_match_count": r.osint_match_count,
                },
            }
            for r in results
        ],
    }
    out_path = "/tmp/deepverify_eval_report.json"
    with open(out_path, "w") as f:
        json.dump(report_dict, f, indent=2)
    print(f"  Full report saved → {out_path}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    print(f"\n{BOLD}{CYAN}🛡  DeepVerify — Batch Ground-Truth Evaluation{RESET}")
    print(f"  {len(EVAL_DATASET)} videos  |  API: {API_BASE}\n")

    # Health check
    async with httpx.AsyncClient() as c:
        try:
            r = await c.get(f"{API_BASE}/health", timeout=5)
            r.raise_for_status()
            print(f"{GREEN}  ✅  Backend healthy: {r.json()}{RESET}\n")
        except Exception as exc:
            print(f"{RED}  ❌  Backend not reachable at {API_BASE}/health — start it first!\n  {exc}{RESET}")
            sys.exit(1)

    # Submit & process all videos concurrently
    print(f"{BOLD}  Submitting all {len(EVAL_DATASET)} jobs concurrently…{RESET}\n")
    t_start = time.time()

    async with httpx.AsyncClient(timeout=None) as client:
        tasks = [
            run_single(client, entry, i)
            for i, entry in enumerate(EVAL_DATASET)
        ]
        results: list[EvalResult] = await asyncio.gather(*tasks)

    total_elapsed = time.time() - t_start
    print(f"\n{GREEN}  All jobs finished in {total_elapsed:.0f}s{RESET}\n")

    metrics = compute_metrics(results)
    print_report(results, metrics)


if __name__ == "__main__":
    asyncio.run(main())
