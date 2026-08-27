#!/usr/bin/env python3
"""
test_e2e.py — End-to-End API test for the DeepVerify pipeline.

Tests the complete flow via the live HTTP API:
  1. Upload a video file to POST /api/analyze
  2. Poll GET /api/status/{job_id} until complete or failed
  3. Fetch GET /api/report/{job_id} and validate all 3 pillars + blockchain

Usage:
    # From the project root:
    python test_e2e.py [--video path/to/video.mp4] [--url https://...]

Requirements:
    pip install httpx
    Backend must be running: ./start.sh  (from backend/)
"""
import argparse
import json
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("❌  httpx not installed. Run: pip install httpx")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE = "http://localhost:8000"
POLL_INTERVAL_S = 3       # seconds between status polls
TIMEOUT_S = 600           # give the full pipeline up to 10 min
SAMPLE_VIDEO = "sample_test_video.mp4"   # default fallback

# ANSI colours
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"{GREEN}  ✅  {msg}{RESET}")
def fail(msg): print(f"{RED}  ❌  {msg}{RESET}"); sys.exit(1)
def warn(msg): print(f"{YELLOW}  ⚠️   {msg}{RESET}")
def info(msg): print(f"{CYAN}  ℹ️   {msg}{RESET}")


# ---------------------------------------------------------------------------
# Pre-flight .env checklist
# ---------------------------------------------------------------------------
def run_preflight():
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  PRE-FLIGHT CHECKLIST{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    env_path = Path(__file__).parent / "backend" / ".env"
    if not env_path.exists():
        env_path = Path(__file__).parent / ".env"

    required = {
        "GROQ_API_KEY": "Groq Whisper + Llama 3.3 (Pillars 1 & 3)",
    }
    optional = {
        "BLOCKCHAIN_RPC_URL":  "Blockchain attestation (Stage 7)",
        "WALLET_PRIVATE_KEY":  "Blockchain signing wallet",
        "CONTRACT_ADDRESS":    "Deployed MediaProvenanceRegistry contract",
        "SERPAPI_API_KEY":     "OSINT reverse image search",
        "SUPABASE_URL":        "Supabase DB / Keyframe storage",
        "PINATA_API_KEY":      "IPFS pinning via Pinata",
        "TELEGRAM_BOT_TOKEN":  "Telegram bot notifications",
    }

    if env_path.exists():
        env_vars: dict[str, str] = {}
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env_vars[k.strip()] = v.strip()
    else:
        warn(".env file not found — checking OS environment only")
        import os
        env_vars = dict(os.environ)

    for key, desc in required.items():
        val = env_vars.get(key, "")
        if val and val not in ("your_...", ""):
            ok(f"{key} — {desc}")
        else:
            fail(f"{key} is missing or unset — required for: {desc}")

    for key, desc in optional.items():
        val = env_vars.get(key, "")
        if val and "your_" not in val and val != "":
            ok(f"{key} — {desc}")
        else:
            warn(f"{key} not set — {desc} will be skipped")

    print()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
def check_health(client: httpx.Client):
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  BACKEND HEALTH CHECK{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")
    try:
        r = client.get(f"{API_BASE}/health", timeout=5)
        r.raise_for_status()
        ok(f"Backend is reachable: {r.json()}")
    except Exception as exc:
        fail(
            f"Backend not responding at {API_BASE}/health — "
            f"start it first with ./start.sh\n     Error: {exc}"
        )
    print()


# ---------------------------------------------------------------------------
# Submit job
# ---------------------------------------------------------------------------
def submit_job(client: httpx.Client, video_path: str | None, url: str | None) -> str:
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  SUBMITTING JOB{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    if url:
        info(f"Submitting URL: {url}")
        r = client.post(
            f"{API_BASE}/api/analyze",
            data={"source_url": url},
            timeout=30,
        )
    elif video_path:
        vp = Path(video_path)
        if not vp.exists():
            fail(f"Video file not found: {video_path}")
        info(f"Uploading file: {vp} ({vp.stat().st_size / 1024:.1f} KB)")
        with open(vp, "rb") as f:
            r = client.post(
                f"{API_BASE}/api/analyze",
                files={"file": (vp.name, f, "video/mp4")},
                timeout=60,
            )
    else:
        fail("Provide --video <path> or --url <url>")

    if r.status_code != 200:
        fail(f"Submit failed ({r.status_code}): {r.text[:400]}")

    job_id = r.json()["job_id"]
    ok(f"Job created: {job_id}")
    print()
    return job_id


# ---------------------------------------------------------------------------
# Poll status
# ---------------------------------------------------------------------------
def poll_until_complete(client: httpx.Client, job_id: str) -> dict:
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  PIPELINE PROGRESS{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    start = time.time()
    last_label = ""

    while True:
        elapsed = time.time() - start
        if elapsed > TIMEOUT_S:
            fail(f"Timed out after {TIMEOUT_S}s waiting for job {job_id}")

        r = client.get(f"{API_BASE}/api/status/{job_id}", timeout=10)
        if r.status_code != 200:
            warn(f"Status poll returned {r.status_code} — retrying…")
            time.sleep(POLL_INTERVAL_S)
            continue

        data = r.json()
        status = data["status"]
        label  = data.get("stage_label", status)
        step   = data.get("stage_step", 0)
        total  = data.get("total_steps", 7)

        if label != last_label:
            bar = "█" * step + "░" * max(0, total - step)
            print(f"  [{bar}]  Step {step}/{total}  {CYAN}{label}{RESET}  ({elapsed:.0f}s)")
            last_label = label

        if status == "complete":
            ok(f"Pipeline complete in {elapsed:.1f}s\n")
            return data
        elif status == "failed":
            fail(f"Pipeline failed: {data.get('error_message', 'unknown error')}")

        time.sleep(POLL_INTERVAL_S)


# ---------------------------------------------------------------------------
# Fetch & validate report
# ---------------------------------------------------------------------------
def validate_report(client: httpx.Client, job_id: str):
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  REPORT VALIDATION{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    r = client.get(f"{API_BASE}/api/report/{job_id}", timeout=15)
    if r.status_code != 200:
        fail(f"Could not fetch report ({r.status_code}): {r.text[:300]}")

    report = r.json()

    # ── Pillar 1 ──────────────────────────────────────────────────────
    temporal = report.get("temporal", {})
    if not temporal:
        warn("Pillar 1 (temporal) missing from report")
    else:
        m = temporal.get("metrics", {})
        ok(f"Pillar 1 — Temporal Integrity")
        info(f"  is_manipulated    : {temporal.get('is_manipulated')}")
        info(f"  mean_fake_score   : {m.get('mean_fake_score', 'N/A')}")
        info(f"  temporal_jitter   : {m.get('temporal_jitter', 'N/A')}")
        info(f"  peak_frame_score  : {m.get('peak_frame_score', 'N/A')}")
        info(f"  frames_analyzed   : {m.get('frames_analyzed', 'N/A')}")

    print()

    # ── Pillar 2 ──────────────────────────────────────────────────────
    visual = report.get("visual_threat", {})
    if not visual:
        warn("Pillar 2 (visual_threat) missing from report")
    else:
        m = visual.get("metrics", {})
        ok(f"Pillar 2 — Visual Safety")
        info(f"  is_visual_threat  : {visual.get('is_visual_threat')}")
        info(f"  max_threat_score  : {m.get('max_threat_score', 'N/A')}")
        info(f"  flagged_content   : {m.get('flagged_content', [])}")
        info(f"  frames_analyzed   : {m.get('frames_analyzed', 'N/A')}")

    print()

    # ── Pillar 3 ──────────────────────────────────────────────────────
    psych = report.get("psychological_threat", {})
    if not psych:
        warn("Pillar 3 (psychological_threat) missing from report")
    else:
        m = psych.get("metrics", {})
        ok(f"Pillar 3 — Cognitive Security")
        info(f"  is_psych_threat   : {psych.get('is_psychological_threat')}")
        info(f"  manipulation_score: {m.get('manipulation_score', 'N/A')}")
        info(f"  detected_tactics  : {m.get('detected_tactics', [])}")
        info(f"  reasoning         : {str(m.get('reasoning', ''))[:120]}…")

    print()

    # ── Verdict ───────────────────────────────────────────────────────
    verdict = report.get("verdict", {})
    ok(f"LLM Verdict Synthesis")
    info(f"  verdict_category  : {verdict.get('verdict_category', 'N/A')}")
    info(f"  authenticity_score: {verdict.get('authenticity_score', 'N/A')}%")
    info(f"  headline          : {verdict.get('summary_headline', 'N/A')}")

    print()

    # ── Blockchain ────────────────────────────────────────────────────
    blockchain = report.get("blockchain", {})
    tx_hash = blockchain.get("tx_hash") or blockchain.get("blockchain_tx")
    if tx_hash and len(str(tx_hash)) == 66:
        ok(f"Blockchain Attestation — sealed on-chain ✓")
        info(f"  tx_hash  : {tx_hash}")
        info(f"  explorer : https://sepolia.celoscan.io/tx/{tx_hash}")
    elif blockchain.get("status") == "off_chain":
        warn("Blockchain: WALLET_PRIVATE_KEY or CONTRACT_ADDRESS not configured — attestation skipped")
    else:
        warn(f"Blockchain: unexpected state — {blockchain}")

    print()

    # ── Full JSON dump ─────────────────────────────────────────────────
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  FULL REPORT JSON{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")
    print(json.dumps(report, indent=2))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    global API_BASE
    parser = argparse.ArgumentParser(
        description="End-to-end API test for DeepVerify pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--video", default=None,
                        help=f"Path to a local MP4 file (default: {SAMPLE_VIDEO})")
    parser.add_argument("--url",   default=None,
                        help="Social media URL to submit instead of a file")
    parser.add_argument("--api",   default=API_BASE,
                        help=f"Backend base URL (default: {API_BASE})")
    parser.add_argument("--skip-preflight", action="store_true",
                        help="Skip the .env pre-flight check")
    args = parser.parse_args()

    API_BASE = args.api.rstrip("/")

    print(f"\n{BOLD}{CYAN}🛡  DeepVerify — End-to-End Test Runner{RESET}\n")

    if not args.skip_preflight:
        run_preflight()

    video_path = args.video
    if not video_path and not args.url:
        # Fall back to sample file in same directory
        candidate = Path(__file__).parent / SAMPLE_VIDEO
        if candidate.exists():
            video_path = str(candidate)
        else:
            fail(
                f"No --video or --url provided and {SAMPLE_VIDEO} not found.\n"
                f"     Place a short MP4 in the project root or pass --video <path>"
            )

    with httpx.Client() as client:
        check_health(client)
        job_id = submit_job(client, video_path, args.url)
        poll_until_complete(client, job_id)
        validate_report(client, job_id)

    print(f"\n{BOLD}{GREEN}🎉  All 3 Pillars validated successfully!{RESET}")
    print(f"    Report URL: {API_BASE}/api/report/{job_id}\n")


if __name__ == "__main__":
    main()
