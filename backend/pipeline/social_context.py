"""
pipeline/social_context.py — Crowd Wisdom Triage Layer for DeepVerify.

Analyzes social media comments to gauge public reaction, extract debunking consensus,
and detect societal panic signals prior to heavy GPU forensic processing.
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Common spam / bot promotion patterns to filter out
_BOT_SPAM_PATTERNS = [
    r'\b(?:dm|message|inbox)\b.*?\b(?:promo|promotion|credit|biz|work)\b',
    r'\b(?:check|see|link)\s+.*?\bbio\b',
    r'\b(?:earn|make)\s+\$?\d+',
    r'\b(?:follow|sub|subscribe)\b.*?\b(?:back|me|channel)\b',
    r'\b(?:crypto|forex|invest|whatsapp)\b',
    r'^(?:first|nice|cool|wow|fire|amaze|awesome|lmao|lol|omg|sub)[\!\.\?]*$',
]
_COMPILED_SPAM_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _BOT_SPAM_PATTERNS]


def fetch_comments(url: str, max_comments: int = 300) -> List[str]:
    """
    Fetch or simulate top user comments from a social media post URL.
    Returns up to `max_comments` comment strings.
    """
    logger.info("fetch_comments called for url: %s (max=%d)", url, max_comments)
    if not url:
        return []

    url_lower = str(url).lower()

    if "panic" in url_lower or "crisis" in url_lower or "riot" in url_lower:
        simulated = [
            "This is terrifying! People need to evacuate immediately!",
            "OMG is this real?! Where is the military?!",
            "This is terrifying! People need to evacuate immediately!",  # duplicate
            "BREAKING: Everyone share this right now before it gets taken down!",
            "Check link in bio to earn $5000 fast",  # bot spam
            "Is the government hiding this from us? Total outrage!",
            "People are panicking in the streets, stay inside everyone!",
            "dm me for promo",  # bot spam
        ]
    elif "debunk" in url_lower or "movie" in url_lower or "fake" in url_lower:
        simulated = [
            "This clip is fake! It is from the 2018 movie CGI sequence, check IMDB.",
            "Guys this was debunked years ago. Original video was posted in 2015 on Vimeo.",
            "This clip is fake! It is from the 2018 movie CGI sequence, check IMDB.",  # duplicate
            "First!",  # bot spam
            "It's a manufactured deepfake created using AI tools.",
            "Stop spreading fake news, this is from a video game trailer.",
            "Check my bio for cheap crypto",  # bot spam
            "Fact check: Snopes already verified this was filmed in Madrid in 2019, not recent.",
        ]
    else:
        simulated = [
            "Interesting video, thanks for sharing.",
            "Is there any source for this claim?",
            "Looks like CGI to me, notice the lighting glitches on the face.",
            "Looks like CGI to me, notice the lighting glitches on the face.",  # duplicate
            "First!",  # bot spam
            "Several people on Twitter pointed out this footage was uploaded back in 2021.",
            "Follow me back guys",  # bot spam
            "Not sure if authentic or generated, waiting for official confirmation.",
            "Can someone fact check this date?",
        ]

    result: List[str] = []
    while len(result) < max_comments:
        for c in simulated:
            result.append(c)
            if len(result) >= max_comments:
                break
        if not simulated:
            break

    return result[:max_comments]


def filter_bot_noise(comments_list: List[Any]) -> List[str]:
    """
    Remove exact string duplicates, whitespace-only entries, and generic bot spam
    to mitigate bot-swarm manipulation while maintaining original comment order.
    """
    if not comments_list:
        return []

    clean_comments: List[str] = []
    seen_normalized = set()

    for item in comments_list:
        if isinstance(item, dict):
            text = item.get("text") or item.get("content") or item.get("comment") or ""
        else:
            text = str(item or "")

        text_str = text.strip()
        if not text_str or len(text_str) < 3:
            continue

        normalized_key = text_str.lower()
        if normalized_key in seen_normalized:
            continue

        is_spam = False
        for pattern in _COMPILED_SPAM_PATTERNS:
            if pattern.search(text_str):
                is_spam = True
                break

        if is_spam:
            continue

        seen_normalized.add(normalized_key)
        clean_comments.append(text_str)

    logger.info("filter_bot_noise: filtered %d comments -> %d clean comments", len(comments_list), len(clean_comments))
    return clean_comments


_SYSTEM_PROMPT = (
    "You are an expert OSINT crowd intelligence analyst specializing in disinformation triage, "
    "bot detection, public reaction analysis, and debunking signal extraction. "
    "Your job is to analyze social media comment sections for crowd consensus, factual debunking citations, "
    "and societal panic indicators. Respond strictly in valid JSON format with no markdown wrappers or extra text."
)

_USER_PROMPT_TEMPLATE = """Analyze the following social media comments related to a post:

Comments to evaluate:
\"\"\"
{formatted_comments}
\"\"\"

Tasks:
1. Determine if the crowd consensus indicates the content is fake, CGI, a movie clip, old recycled footage, or previously debunked (noting specific sources or dates cited by users).
2. Quantify societal panic: measure fear, outrage, panic, or incitement/mobilization expressed by commentators.
3. Extract explicit factual assertions or debunking claims made by users.

Respond ONLY with a valid JSON object matching this exact schema:
{{
  "debunk_consensus": <float between 0.0 and 1.0>,
  "societal_panic_index": <integer between 0 and 100>,
  "extracted_claims": [<list of strings containing specific factual claims or debunk points>]
}}"""


def analyze_crowd_consensus(clean_comments: List[str]) -> Dict[str, Any]:
    """
    Formats cleaned comments and sends them to the LLM to compute:
      - debunk_consensus (float 0.0 - 1.0)
      - societal_panic_index (int 0 - 100)
      - extracted_claims (list of strings)

    Wrapped in a strict try/except block to guarantee pipeline safety.
    If empty, timing out, or failing, returns neutral defaults (debunk_consensus=0.5, panic=0).
    """
    if not clean_comments:
        logger.info("analyze_crowd_consensus: clean_comments is empty — returning neutral default")
        return {
            "debunk_consensus": 0.5,
            "societal_panic_index": 0,
            "extracted_claims": [],
            "error": None,
        }

    try:
        groq_api_key = None
        openai_api_key = None
        try:
            from config import get_settings
            settings = get_settings()
            groq_api_key = settings.groq_api_key
            openai_api_key = settings.openai_api_key
        except Exception as set_exc:
            logger.warning("analyze_crowd_consensus: Settings load error: %s", set_exc)

        selected_comments = clean_comments[:80]
        formatted_comments = "\n".join(f"- {c}" for c in selected_comments)
        user_prompt = _USER_PROMPT_TEMPLATE.format(formatted_comments=formatted_comments)

        raw_json_str = None

        if groq_api_key and groq_api_key.strip():
            from groq import Groq
            client = Groq(api_key=groq_api_key)
            response = client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout=25,
            )
            raw_json_str = response.choices[0].message.content or "{}"
        elif openai_api_key and openai_api_key.strip():
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout=25,
            )
            raw_json_str = response.choices[0].message.content or "{}"
        else:
            logger.warning("analyze_crowd_consensus: Neither Groq nor OpenAI API key configured — returning neutral fallback")
            return {
                "debunk_consensus": 0.5,
                "societal_panic_index": 0,
                "extracted_claims": [],
                "error": "No LLM API key available",
            }

        cleaned_str = raw_json_str.strip()
        if cleaned_str.startswith("```json"):
            cleaned_str = cleaned_str[7:]
        if cleaned_str.startswith("```"):
            cleaned_str = cleaned_str[3:]
        if cleaned_str.endswith("```"):
            cleaned_str = cleaned_str[:-3]
        cleaned_str = cleaned_str.strip()

        parsed = json.loads(cleaned_str)

        debunk_raw = parsed.get("debunk_consensus", 0.5)
        try:
            debunk_consensus = float(debunk_raw)
            debunk_consensus = max(0.0, min(1.0, round(debunk_consensus, 3)))
        except (TypeError, ValueError):
            debunk_consensus = 0.5

        panic_raw = parsed.get("societal_panic_index", 0)
        try:
            panic_index = int(round(float(panic_raw)))
            panic_index = max(0, min(100, panic_index))
        except (TypeError, ValueError):
            panic_index = 0

        extracted_claims = parsed.get("extracted_claims", [])
        if not isinstance(extracted_claims, list):
            extracted_claims = []
        extracted_claims = [str(claim).strip() for claim in extracted_claims if claim]

        logger.info(
            "analyze_crowd_consensus: debunk=%.2f, panic=%d, claims_count=%d",
            debunk_consensus, panic_index, len(extracted_claims)
        )

        return {
            "debunk_consensus": debunk_consensus,
            "societal_panic_index": panic_index,
            "extracted_claims": extracted_claims,
            "error": None,
        }

    except Exception as exc:
        logger.error("analyze_crowd_consensus exception (graceful fallback to neutral): %s", exc)
        return {
            "debunk_consensus": 0.5,
            "societal_panic_index": 0,
            "extracted_claims": [],
            "error": str(exc),
        }
