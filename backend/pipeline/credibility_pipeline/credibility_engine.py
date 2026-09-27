"""
credibility_engine.py — OSINT evidence retrieval and domain credibility scoring.

Configuration
-------------
Evidence is retrieved via DuckDuckGo Instant Answer / search.  No paid API key
is required.  The optional environment variable ``EVIDENCE_SEARCH_TIMEOUT``
(default 10 s) controls the per-request HTTP timeout.

Behaviour contract
------------------
* Evidence is retrieved by querying the assertion text against a web-search
  shim.  Each snippet is analysed for stance (supports / refutes / neutral)
  using simple keyword heuristics.
* If credentials are missing, retrieval fails, or evidence is insufficient the
  function returns ``Uncertain`` with an honest explanation and an audit entry.
* Mock / fabricated citations are **never** returned in production.  Test
  fixtures must be injected via the ``_inject_evidence_for_test`` hook.
"""
import os
import time
import logging
import re
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database import Assertion, EvidenceItem, EvidenceStance
from pipeline.audit_logger import record_audit_stage

logger = logging.getLogger("deepverify.credibility_engine")

# ---------------------------------------------------------------------------
# Domain reputation map (used for credibility scoring of retrieved sources)
# ---------------------------------------------------------------------------
DOMAIN_REPUTATION = {
    "reuters.com": 0.95,
    "apnews.com": 0.95,
    "bbc.com": 0.90,
    "bbc.co.uk": 0.90,
    "factcheck.org": 0.92,
    "snopes.com": 0.90,
    "politifact.com": 0.88,
    "wikipedia.org": 0.80,
    "nature.com": 0.98,
    "science.org": 0.98,
    "who.int": 0.95,
    "cdc.gov": 0.95,
}

# ---------------------------------------------------------------------------
# Test-only injection hook (populated exclusively in unit tests)
# ---------------------------------------------------------------------------
# When non-None this dict is keyed by assertion_text (str) and maps to a list
# of raw evidence dicts (same schema as _fetch_via_duckduckgo).  The
# production code path ignores this entirely.
_TEST_EVIDENCE_REGISTRY: Optional[dict] = None


def _inject_evidence_for_test(registry: Optional[dict]) -> None:
    """
    **Test-only.**  Call from fixtures to pre-load evidence without hitting
    the network.  Pass ``None`` to clear the registry and restore live
    behaviour.
    """
    global _TEST_EVIDENCE_REGISTRY
    _TEST_EVIDENCE_REGISTRY = registry


def calculate_domain_credibility(source_name: str, source_url: str) -> float:
    """Evaluate source credibility based on domain reputation."""
    for domain, score in DOMAIN_REPUTATION.items():
        if domain in source_url.lower() or domain in source_name.lower():
            return score
    return 0.70  # Default baseline score for general web sources


# ---------------------------------------------------------------------------
# Stance inference from snippet text
# ---------------------------------------------------------------------------
_REFUTE_KEYWORDS = [
    "false", "debunked", "misinformation", "not true", "incorrect",
    "fabricated", "misleading", "hoax", "no evidence", "denied",
    "refuted", "disproved", "wrong", "fake", "fiction",
]
_SUPPORT_KEYWORDS = [
    "confirmed", "verified", "true", "accurate", "correct",
    "supported by", "evidence shows", "study finds", "researchers found",
    "proven", "official", "scientists say", "data shows",
]


def _infer_stance(snippet: str, assertion_text: str) -> EvidenceStance:
    """
    Infer whether a search snippet supports, refutes, or is neutral toward
    the assertion.  Returns EvidenceStance.NEUTRAL when ambiguous.

    Note: A trusted domain alone does NOT prove a claim—the snippet content
    itself must be evaluated.
    """
    text = snippet.lower()
    refute_hits = sum(1 for kw in _REFUTE_KEYWORDS if kw in text)
    support_hits = sum(1 for kw in _SUPPORT_KEYWORDS if kw in text)

    if refute_hits > support_hits:
        return EvidenceStance.REFUTES
    if support_hits > refute_hits:
        return EvidenceStance.SUPPORTS
    return EvidenceStance.NEUTRAL


# ---------------------------------------------------------------------------
# Evidence retrieval via DuckDuckGo Instant Answer API (no API key required)
# ---------------------------------------------------------------------------

def _fetch_via_duckduckgo(assertion_text: str) -> List[dict]:
    """
    Query the DuckDuckGo Instant Answer JSON API for the assertion text.
    Returns a list of raw evidence dicts or an empty list on any failure.

    Uses only stdlib + the ``requests`` package (already in requirements.txt
    as a transitive dependency of several existing deps).
    """
    try:
        import requests  # type: ignore

        timeout = int(os.getenv("EVIDENCE_SEARCH_TIMEOUT", "10"))
        params = {
            "q": assertion_text[:200],
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params=params,
            timeout=timeout,
            headers={"User-Agent": "DeepVerify/1.0 (fact-checking research)"},
        )
        resp.raise_for_status()
        data = resp.json()

        results: List[dict] = []

        # Abstract (top-level answer)
        abstract_text = data.get("AbstractText", "").strip()
        abstract_url = data.get("AbstractURL", "").strip()
        abstract_source = data.get("AbstractSource", "").strip()
        if abstract_text and abstract_url:
            results.append({
                "source_name": abstract_source or "DuckDuckGo Abstract",
                "source_url": abstract_url,
                "content_snippet": abstract_text[:500],
            })

        # Related topics
        for topic in data.get("RelatedTopics", [])[:4]:
            if not isinstance(topic, dict):
                continue
            snippet = topic.get("Text", "").strip()
            first_url = topic.get("FirstURL", "").strip()
            if snippet and first_url:
                domain_match = re.search(r"https?://(?:www\.)?([^/]+)", first_url)
                src_name = domain_match.group(1) if domain_match else "Web"
                results.append({
                    "source_name": src_name,
                    "source_url": first_url,
                    "content_snippet": snippet[:500],
                })

        return results

    except Exception as exc:
        logger.warning("[credibility_engine] DuckDuckGo retrieval failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_evidence_for_assertion(
    session: AsyncSession,
    assertion: Assertion,
) -> List[EvidenceItem]:
    """
    Retrieve real evidence for *assertion* and persist EvidenceItem records.

    Behaviour:
    * In unit tests: returns items from ``_TEST_EVIDENCE_REGISTRY`` if the
      assertion text is registered there.  No network calls are made.
    * In production: queries DuckDuckGo and infers stance from retrieved
      snippets.
    * If no evidence is found (network failure, empty result, etc.) a single
      EvidenceItem with stance=NEUTRAL and a candid explanation is written so
      the caller can surface ``Uncertain`` to the user without fabricating
      citations.
    """
    start_time = time.time()
    assertion_text = assertion.assertion_text

    # Resolve raw evidence dicts
    if _TEST_EVIDENCE_REGISTRY is not None:
        # Test mode: look up pre-injected evidence
        raw_items: List[dict] = list(_TEST_EVIDENCE_REGISTRY.get(assertion_text, []))
        retrieval_method = "test_fixture"
    else:
        # Production mode: live retrieval
        raw_items = _fetch_via_duckduckgo(assertion_text)
        retrieval_method = "duckduckgo"

    # Infer stance and build EvidenceItem records
    items: List[EvidenceItem] = []
    for raw in raw_items:
        snippet = raw.get("content_snippet", "")
        src_url = raw.get("source_url", "")
        src_name = raw.get("source_name", src_url or "Unknown")

        stance = _infer_stance(snippet, assertion_text)
        cred = calculate_domain_credibility(src_name, src_url)

        item = EvidenceItem(
            assertion_id=assertion.id,
            source_name=src_name,
            source_url=src_url,
            content_snippet=snippet,
            stance=stance,
            credibility_score=cred,
        )
        session.add(item)
        items.append(item)

    # Fallback: no evidence found
    if not items:
        reason = (
            f"No evidence was retrieved for the assertion: '{assertion_text[:120]}'. "
            f"Retrieval method: {retrieval_method}. "
            "The system could not locate relevant sources; verdict will be Uncertain."
        )
        logger.warning("[credibility_engine] %s", reason)
        item = EvidenceItem(
            assertion_id=assertion.id,
            source_name="DeepVerify Evidence Retrieval",
            source_url="",
            content_snippet=reason,
            stance=EvidenceStance.NEUTRAL,
            credibility_score=0.0,
        )
        session.add(item)
        items.append(item)

    await session.commit()

    await record_audit_stage(
        session=session,
        claim_id=assertion.claim_id,
        stage_name="EVIDENCE_RETRIEVAL",
        input_summary=(
            f"Query assertion: '{assertion_text[:60]}' "
            f"via {retrieval_method}"
        ),
        output_summary=(
            f"Retrieved {len(items)} evidence item(s); stances: "
            + ", ".join(
                f"{i.stance.value}({i.credibility_score:.2f})" for i in items
            )
        ),
        start_time=start_time,
    )

    return items
