"""
pipeline/c2pa_inspector.py — C2PA Content Credentials cryptographic inspection.

Uses the modern c2pa-python (v0.6+) API:
  reader = c2pa.Reader.from_file(path)
  data   = json.loads(reader.json())

Parses the manifest store JSON for:
  - digitalSourceType (e.g. trainedAlgorithmicMedia, compositeWithTrainedAlgorithmicMedia)
  - Generator assertions (Adobe Firefly, OpenAI Sora, Stability AI, etc.)
  - Certificate issuer / signing identity

Returns a typed C2PAResult dataclass. Never raises — on any error (no
manifest, unsupported format, corrupt file), returns status="no_manifest"
or status="error" with an explanatory message.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Known digitalSourceType values that indicate AI generation
AI_SOURCE_TYPES = {
    "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    "http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia",
    "trainedAlgorithmicMedia",
    "compositeWithTrainedAlgorithmicMedia",
}

# Known AI generator labels in assertion data
AI_GENERATOR_KEYWORDS = {
    "adobe firefly", "openai", "sora", "dall-e", "stability ai",
    "midjourney", "runway", "pika", "kling", "gen-2", "gen-3",
    "heygen", "synthesia", "deepfake", "elevenlabs",
}


@dataclass
class C2PAResult:
    status: str                             # "signed_ai" | "signed_authentic" | "no_manifest" | "error"
    is_ai_generated: bool = False
    digital_source_type: Optional[str] = None
    issuer: Optional[str] = None
    generator: Optional[str] = None        # Name of AI tool if detected
    assertions: list[dict] = field(default_factory=list)
    raw_manifest: Optional[dict] = None
    message: str = ""


def inspect(file_path: str) -> C2PAResult:
    """
    Inspect a media file for C2PA Content Credentials.
    Safe to call on any file — returns gracefully if no manifest is found.
    """
    try:
        import c2pa  # type: ignore
    except ImportError:
        logger.error("c2pa-python is not installed. Run: pip install c2pa-python")
        return C2PAResult(status="error", message="c2pa-python not installed")

    try:
        # c2pa-python ≥0.6: Reader.from_file(path)
        # c2pa-python ≥1.0: Reader(path)  (constructor-style)
        # Try both so we handle any installed version gracefully.
        try:
            reader = c2pa.Reader(file_path)  # type: ignore
        except (AttributeError, TypeError):
            reader = c2pa.Reader.from_file(file_path)  # type: ignore
    except Exception as exc:
        exc_str = str(exc).lower()
        # Common non-fatal cases: no manifest embedded, unsupported format
        if any(kw in exc_str for kw in ("no manifest", "not found", "unsupported", "jumbf")):
            logger.info("C2PA: No manifest found in %s", file_path)
            return C2PAResult(
                status="no_manifest",
                message="No C2PA Content Credentials embedded in this file.",
            )
        logger.warning("C2PA read error for %s: %s", file_path, exc)
        return C2PAResult(
            status="error",
            message=f"C2PA inspection failed: {exc}",
        )

    try:
        raw_json_str = reader.json()
        manifest_store = json.loads(raw_json_str)
    except Exception as exc:
        logger.warning("C2PA JSON parse error: %s", exc)
        return C2PAResult(
            status="error",
            message=f"C2PA manifest JSON could not be parsed: {exc}",
        )

    return _parse_manifest_store(manifest_store)


def _parse_manifest_store(store: dict) -> C2PAResult:
    """Walk the parsed manifest store and extract relevant fields."""
    assertions_found: list[dict] = []
    digital_source_type: Optional[str] = None
    issuer: Optional[str] = None
    generator: Optional[str] = None
    is_ai = False

    # The active manifest is referenced by store["active_manifest"]
    active_label = store.get("active_manifest")
    manifests: dict = store.get("manifests", {})

    # Prefer the active manifest; fall back to iterating all manifests
    manifest_candidates = []
    if active_label and active_label in manifests:
        manifest_candidates = [manifests[active_label]]
    else:
        manifest_candidates = list(manifests.values())

    for manifest in manifest_candidates:
        # --- Extract signing certificate issuer ---
        sig_info = manifest.get("signature_info") or manifest.get("signatureInfo") or {}
        if not issuer:
            issuer = (
                sig_info.get("issuer")
                or sig_info.get("cert_serial_number")
                or sig_info.get("time")
            )

        # --- Walk assertions ---
        for assertion in manifest.get("assertions", []):
            label: str = assertion.get("label", "")
            data: dict = assertion.get("data", {})
            assertions_found.append({"label": label, "data": data})

            # digitalSourceType check
            src_type = data.get("digitalSourceType") or data.get("digital_source_type")
            if src_type and not digital_source_type:
                digital_source_type = src_type
                if src_type in AI_SOURCE_TYPES:
                    is_ai = True

            # Generator / software agent check
            if "c2pa.generator" in label or "stds.schema-org.CreativeWork" in label:
                agent = (
                    data.get("@type")
                    or data.get("name")
                    or data.get("softwareAgent")
                    or ""
                )
                if not generator:
                    generator = str(agent)
                # Check against known AI tools
                agent_lower = str(agent).lower()
                if any(kw in agent_lower for kw in AI_GENERATOR_KEYWORDS):
                    is_ai = True

            # Actions assertion — look for AI editing actions
            if "c2pa.actions" in label:
                for action in data.get("actions", []):
                    action_label = action.get("action", "")
                    # c2pa.created via AI tools
                    if "ai" in action_label.lower() or "train" in action_label.lower():
                        is_ai = True
                    sw_agent = action.get("softwareAgent", "")
                    if any(kw in str(sw_agent).lower() for kw in AI_GENERATOR_KEYWORDS):
                        is_ai = True
                        if not generator:
                            generator = str(sw_agent)

    if not assertions_found and not manifests:
        return C2PAResult(
            status="no_manifest",
            message="Manifest store is empty — no C2PA credentials found.",
        )

    status = "signed_ai" if is_ai else "signed_authentic"
    message = (
        f"File is cryptographically signed as AI-generated via C2PA. "
        f"Generator: {generator or 'Unknown'}. Source type: {digital_source_type or 'N/A'}."
        if is_ai
        else "File carries valid C2PA Content Credentials with no AI-generation assertions."
    )

    logger.info("C2PA result: status=%s, issuer=%s, generator=%s", status, issuer, generator)

    return C2PAResult(
        status=status,
        is_ai_generated=is_ai,
        digital_source_type=digital_source_type,
        issuer=issuer,
        generator=generator,
        assertions=assertions_found,
        raw_manifest=store,
        message=message,
    )
