"""
config.py — Environment variable validation & settings.

Fails fast at startup with explicit, descriptive error messages if
any required API key is missing or blank.

Services covered:
  - OpenAI (LLM synthesis)
  - Groq (Whisper audio transcription)
  - SerpApi (Google Lens reverse image search)
  - Supabase (optional: cloud DB + storage)
  - Telegram Bot (optional: completion notifications)
"""
import os
import sys
import logging
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import Optional

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM Provider ─────────────────────────────────────────────────────
    llm_provider: str = "openai"

    # ── API Keys (required) ───────────────────────────────────────────────
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    serpapi_api_key: str = ""
    resemble_api_key: str = ""

    # ── Supabase (optional — activates cloud DB & storage) ────────────────
    supabase_url: str = ""
    supabase_service_key: str = ""

    # ── Telegram Bot (optional — sends verdict notification on completion) ─
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ── Database ──────────────────────────────────────────────────────────
    # SQLite by default; swap to postgresql+asyncpg://... for Supabase/prod
    database_url: str = "sqlite+aiosqlite:///./deepfake.db"

    # ── Server URLs ───────────────────────────────────────────────────────
    api_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    # ── Optional ML weights ───────────────────────────────────────────────
    model_weights_path: str = ""

    # ── Yt-Dlp Config ─────────────────────────────────────────────────────
    cookies_file_path: str = ""

    # ── Blockchain / IPFS Provenance (all optional) ───────────────────────
    # Polygon Amoy testnet RPC — swap to Sepolia or mainnet as needed
    blockchain_rpc_url: str = "https://rpc-amoy.polygon.technology"
    # Hex private key (0x-prefixed) of the hot-wallet that signs attestations
    wallet_private_key: str = ""
    # Address of the deployed MediaProvenanceRegistry contract
    contract_address: str = ""
    # Pinata credentials for IPFS pinning
    pinata_api_key: str = ""
    pinata_secret_api_key: str = ""
    # Block explorer base URL (no trailing slash)
    block_explorer_url: str = "https://amoy.polygonscan.com"

    # ── Limits ────────────────────────────────────────────────────────────
    max_video_size_mb: int = 500
    frame_sample_rate: int = 1

    # ── Derived helpers ───────────────────────────────────────────────────
    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url.strip() and self.supabase_service_key.strip())

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token.strip() and self.telegram_chat_id.strip())

    @property
    def blockchain_enabled(self) -> bool:
        """True only when both the signing key AND contract address are present."""
        return bool(self.wallet_private_key.strip() and self.contract_address.strip())

    @property
    def pinata_enabled(self) -> bool:
        """True when both Pinata API credentials are present."""
        return bool(self.pinata_api_key.strip() and self.pinata_secret_api_key.strip())

    # ── Validators ────────────────────────────────────────────────────────

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ("openai", "anthropic", "groq"):
            raise ValueError(
                f"LLM_PROVIDER must be 'openai', 'anthropic', or 'groq', got '{v}'"
            )
        return v

    @model_validator(mode="after")
    def validate_required_keys(self) -> "Settings":
        # Fallback check for alternative env var names (e.g., PRIVATE_KEY vs WALLET_PRIVATE_KEY)
        if not self.wallet_private_key and os.getenv("PRIVATE_KEY"):
            object.__setattr__(self, "wallet_private_key", os.getenv("PRIVATE_KEY", "").strip())

        errors: list[str] = []
        warnings: list[str] = []

        # ── Always required ───────────────────────────────────────────────
        if not self.groq_api_key.strip():
            errors.append(
                "GROQ_API_KEY is missing. "
                "Get one free at https://console.groq.com/ — needed for audio transcription."
            )

        if not self.serpapi_api_key.strip():
            errors.append(
                "SERPAPI_API_KEY is missing. "
                "Get one at https://serpapi.com/ — needed for reverse image OSINT."
            )

        # ── Provider-conditional ──────────────────────────────────────────
        if self.llm_provider == "openai" and not self.openai_api_key.strip():
            errors.append(
                "OPENAI_API_KEY is missing. "
                "Get one at https://platform.openai.com/api-keys — required because LLM_PROVIDER=openai."
            )
        if self.llm_provider == "anthropic" and not self.anthropic_api_key.strip():
            errors.append(
                "ANTHROPIC_API_KEY is missing. "
                "Get one at https://console.anthropic.com/ — required because LLM_PROVIDER=anthropic."
            )
        if self.llm_provider == "groq" and not self.groq_api_key.strip():
            errors.append(
                "GROQ_API_KEY is missing. "
                "Get one at https://console.groq.com/ — required because LLM_PROVIDER=groq."
            )

        # ── Optional: warn if partially configured ────────────────────────
        supabase_partial = bool(self.supabase_url.strip()) != bool(self.supabase_service_key.strip())
        if supabase_partial:
            warnings.append(
                "Supabase is partially configured — set BOTH SUPABASE_URL and SUPABASE_SERVICE_KEY "
                "to enable cloud DB. Currently falling back to SQLite."
            )

        telegram_partial = bool(self.telegram_bot_token.strip()) != bool(self.telegram_chat_id.strip())
        if telegram_partial:
            warnings.append(
                "Telegram is partially configured — set BOTH TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID "
                "to enable verdict notifications."
            )

        blockchain_partial = (
            bool(self.wallet_private_key.strip()) != bool(self.contract_address.strip())
        )
        if blockchain_partial:
            warnings.append(
                "Blockchain provenance is partially configured — set BOTH WALLET_PRIVATE_KEY and "
                "CONTRACT_ADDRESS to enable on-chain attestations. Running in off-chain mode."
            )

        pinata_partial = (
            bool(self.pinata_api_key.strip()) != bool(self.pinata_secret_api_key.strip())
        )
        if pinata_partial:
            warnings.append(
                "Pinata is partially configured — set BOTH PINATA_API_KEY and PINATA_SECRET_API_KEY "
                "to enable IPFS pinning. Reports will not be pinned."
            )

        # ── Emit warnings ─────────────────────────────────────────────────
        if warnings:
            for w in warnings:
                logger.warning("⚠️  %s", w)

        # ── Fatal errors ──────────────────────────────────────────────────
        if errors:
            separator = "=" * 70
            lines = [
                "",
                separator,
                "STARTUP FAILED — Missing or invalid environment variables:",
                separator,
                *[f"  ❌  {e}" for e in errors],
                "",
                "  → Edit backend/.env and fill in the missing values.",
                "  → See backend/.env.example for all available settings.",
                separator,
            ]
            msg = "\n".join(lines)
            logger.critical(msg)
            print(msg, file=sys.stderr)
            raise EnvironmentError(msg)

        # ── Startup summary ───────────────────────────────────────────────
        logger.info("✅ Config loaded successfully:")
        logger.info("   LLM provider  : %s", self.llm_provider.upper())
        logger.info("   Database      : %s", "Supabase PostgreSQL" if "supabase" in self.database_url else "SQLite (local)")
        logger.info("   Supabase      : %s", "enabled" if self.supabase_enabled else "disabled (using local DB)")
        logger.info("   Telegram bot  : %s", "enabled" if self.telegram_enabled else "disabled")
        logger.info("   Blockchain    : %s", "enabled (on-chain)" if self.blockchain_enabled else "disabled (off-chain mode)")
        logger.info("   IPFS/Pinata   : %s", "enabled" if self.pinata_enabled else "disabled (no IPFS pinning)")

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Call once at startup; raises EnvironmentError on bad config."""
    return Settings()
