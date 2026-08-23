"""
pipeline/blockchain_service.py — Decentralized Provenance & Chain-of-Custody

Handles:
  1. SHA-256 exact hash of raw video bytes
  2. Perceptual hash (pHash) from video keyframes via imagehash
  3. IPFS pinning of the complete forensic report JSON via Pinata REST API
  4. Smart contract attestation via web3.py (recordAttestation)

Graceful degradation:
  - If WALLET_PRIVATE_KEY / CONTRACT_ADDRESS are absent → returns off_chain status
  - If PINATA_API_KEY / PINATA_SECRET_API_KEY are absent → skips IPFS pinning
  - All exceptions are caught and logged; this service NEVER raises to the caller
"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Verdict string → enum index mapping (matches Solidity Verdict enum order) ──
_VERDICT_MAP = {
    "Authentic":             0,
    "AI-Generated Deepfake": 1,
    "Out-of-Context Cheapfake": 2,
    "Manipulated Audio":     3,
    "Inconclusive":          4,
}


class BlockchainService:
    """
    Orchestrates hashing, IPFS pinning, and smart-contract attestation.

    Instantiate once per job; call run() with the assembled final_result dict.
    """

    # ── Public entry point ────────────────────────────────────────────────────

    def run(
        self,
        job_id: str,
        video_path: str,
        report_payload: dict,
        authenticity_score: int,
        verdict_category: str,
        attributed_source: str,
    ) -> dict:
        """
        Full provenance pipeline.  Always returns a dict; never raises.

        Return dict shape:
          {
            "status":   "sealed" | "off_chain" | "pending",
            "sha256":   "<hex>",
            "phash":    "<str>",
            "ipfs_cid": "<cid>" | None,
            "tx_hash":  "<0x...>" | None,
            "timestamp": "<iso-string>" | None,
          }
        """
        try:
            from config import get_settings
            settings = get_settings()

            # Step 1: Hashing
            sha256_hex, phash_str = self._compute_hashes(video_path)
            logger.info("[%s] Blockchain: SHA-256=%s  pHash=%s", job_id, sha256_hex[:16] + "…", phash_str)

            # Step 2: IPFS pinning
            ipfs_cid: Optional[str] = None
            if settings.pinata_enabled:
                ipfs_cid = self._pin_to_ipfs(report_payload, job_id)
                if ipfs_cid:
                    logger.info("[%s] Blockchain: pinned to IPFS CID=%s", job_id, ipfs_cid)
                else:
                    logger.warning("[%s] Blockchain: IPFS pinning failed — continuing without CID", job_id)
            else:
                logger.info("[%s] Blockchain: Pinata not configured — skipping IPFS pin", job_id)

            # Step 3: On-chain attestation
            if not settings.blockchain_enabled:
                logger.info(
                    "[%s] Blockchain: WALLET_PRIVATE_KEY / CONTRACT_ADDRESS not set — "
                    "running in off_chain mode",
                    job_id,
                )
                return {
                    "status":    "off_chain",
                    "sha256":    sha256_hex,
                    "phash":     phash_str,
                    "ipfs_cid":  ipfs_cid,
                    "tx_hash":   None,
                    "timestamp": None,
                }

            tx_hash, timestamp = self._record_attestation(
                sha256_hex=sha256_hex,
                phash=phash_str,
                ipfs_cid=ipfs_cid or "",
                score=min(100, max(0, int(authenticity_score))),
                verdict_category=verdict_category,
                attributed_source=attributed_source,
                settings=settings,
                job_id=job_id,
            )

            return {
                "status":    "sealed",
                "sha256":    sha256_hex,
                "phash":     phash_str,
                "ipfs_cid":  ipfs_cid,
                "tx_hash":   tx_hash,
                "timestamp": timestamp,
            }

        except Exception as exc:
            logger.exception("[%s] Blockchain: unhandled error in run(): %s", job_id, exc)
            # Never crash the pipeline — return a minimal off_chain payload
            return {
                "status":    "off_chain",
                "sha256":    None,
                "phash":     None,
                "ipfs_cid":  None,
                "tx_hash":   None,
                "timestamp": None,
                "error":     str(exc),
            }

    # ── Step 1: Hashing ───────────────────────────────────────────────────────

    def _compute_hashes(self, video_path: str) -> tuple[str, str]:
        """
        Returns (sha256_hex, phash_str).

        SHA-256: streamed over raw file bytes (large-file safe).
        pHash: computed from up to 5 uniformly-spaced keyframes using imagehash.
        """
        sha256_hex = self._sha256_file(video_path)
        phash_str = self._phash_video(video_path)
        return sha256_hex, phash_str

    @staticmethod
    def _sha256_file(path: str, chunk_size: int = 1 << 20) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _phash_video(path: str, n_frames: int = 5) -> str:
        """
        Extracts n_frames uniformly-spaced frames and returns the pHash of the
        most representative (median fingerprint) frame as a hex string.
        Falls back to "0000000000000000" if any import or decode error occurs.
        """
        try:
            import cv2
            import imagehash
            from PIL import Image
            import numpy as np

            cap = cv2.VideoCapture(path)
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total <= 0:
                cap.release()
                return "0000000000000000"

            # Sample positions
            positions = [int(total * i / n_frames) for i in range(n_frames)]
            hashes: list[imagehash.ImageHash] = []

            for pos in positions:
                cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
                ret, frame = cap.read()
                if not ret:
                    continue
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)
                hashes.append(imagehash.phash(pil_img))

            cap.release()

            if not hashes:
                return "0000000000000000"

            # Return the hash value of the median frame
            # (least distance to the average — representative fingerprint)
            avg_hash = sum(int(str(h), 16) for h in hashes) // len(hashes)
            best = min(hashes, key=lambda h: abs(int(str(h), 16) - avg_hash))
            return str(best)

        except Exception as e:
            logger.warning("pHash computation failed (%s); returning zero sentinel", e)
            return "0000000000000000"

    # ── Step 2: IPFS Pinning via Pinata REST API ──────────────────────────────

    def _pin_to_ipfs(self, report_payload: dict, job_id: str) -> Optional[str]:
        """
        PINs the report JSON to IPFS via Pinata v3 REST API.
        Returns the IPFS CID string, or None on any failure.
        """
        try:
            import httpx
            from config import get_settings
            settings = get_settings()

            pinata_body = {
                "pinataOptions": {"cidVersion": 1},
                "pinataMetadata": {
                    "name": f"deepverify-report-{job_id}",
                    "keyvalues": {"job_id": job_id},
                },
                "pinataContent": report_payload,
            }

            headers = {
                "pinata_api_key":        settings.pinata_api_key,
                "pinata_secret_api_key": settings.pinata_secret_api_key,
                "Content-Type":          "application/json",
            }

            resp = httpx.post(
                "https://api.pinata.cloud/pinning/pinJSONToIPFS",
                headers=headers,
                json=pinata_body,
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("IpfsHash")

        except Exception as e:
            logger.warning("[%s] Blockchain: Pinata pin failed: %s", job_id, e)
            return None

    # ── Step 3: Smart Contract Attestation ───────────────────────────────────

    def _record_attestation(
        self,
        sha256_hex: str,
        phash: str,
        ipfs_cid: str,
        score: int,
        verdict_category: str,
        attributed_source: str,
        settings,
        job_id: str,
    ) -> tuple[str, str]:
        """
        Builds, signs, and broadcasts a recordAttestation() transaction.

        Returns (tx_hash_hex, iso_timestamp_str).
        Raises on any Web3 / RPC error (caller handles gracefully).
        """
        from web3 import Web3
        from web3.middleware import ExtraDataToPOAMiddleware
        from datetime import datetime, timezone

        # Connect
        w3 = Web3(Web3.HTTPProvider(settings.blockchain_rpc_url))
        # Inject PoA middleware required for Polygon and some testnets
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if not w3.is_connected():
            raise ConnectionError(
                f"Cannot connect to RPC: {settings.blockchain_rpc_url}"
            )

        # Load ABI
        abi_path = Path(__file__).parent.parent / "abi" / "MediaProvenanceRegistry.json"
        with open(abi_path) as f:
            abi = json.load(f)

        # Build account from private key
        account = w3.eth.account.from_key(settings.wallet_private_key)
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(settings.contract_address),
            abi=abi,
        )

        # Convert verdict string → enum index
        verdict_index = _VERDICT_MAP.get(verdict_category, 4)  # default Inconclusive

        # Convert sha256 hex → bytes32
        sha256_bytes32 = bytes.fromhex(sha256_hex)

        # Build transaction
        nonce = w3.eth.get_transaction_count(account.address)
        gas_price = w3.eth.gas_price

        tx = contract.functions.recordAttestation(
            sha256_bytes32,
            phash,
            ipfs_cid,
            score,
            verdict_index,
            attributed_source or "Unknown",
        ).build_transaction({
            "from":     account.address,
            "nonce":    nonce,
            "gasPrice": gas_price,
        })

        # Estimate gas (with a 20% buffer)
        estimated_gas = w3.eth.estimate_gas(tx)
        tx["gas"] = int(estimated_gas * 1.2)

        # Sign + send
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=settings.wallet_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        logger.info("[%s] Blockchain: tx sent, waiting for receipt… hash=%s", job_id, tx_hash.hex())

        # Wait for confirmation (up to 30s)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

        if receipt["status"] != 1:
            raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")

        logger.info(
            "[%s] Blockchain: tx CONFIRMED in block %s  hash=%s",
            job_id, receipt["blockNumber"], tx_hash.hex(),
        )

        iso_timestamp = datetime.now(timezone.utc).isoformat()
        return tx_hash.hex(), iso_timestamp
