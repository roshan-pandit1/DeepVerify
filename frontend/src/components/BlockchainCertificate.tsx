"use client";

/**
 * BlockchainCertificate.tsx
 *
 * Displays the on-chain provenance certificate for a forensic report.
 * Renders in two visual modes:
 *   - "sealed"    → green badge, clickable Polygonscan + IPFS links
 *   - "off_chain" → amber badge, hashes only (no links)
 *
 * Designed to match the existing light-theme system (globals.css variables).
 */

import { useState } from "react";
import {
  ShieldCheck,
  ShieldOff,
  ExternalLink,
  Copy,
  CheckCheck,
  Link as LinkIcon,
  Hash,
  Clock,
  Fingerprint,
  Blocks,
} from "lucide-react";
import type { BlockchainResult } from "../../lib/api";

interface BlockchainCertificateProps {
  data?: BlockchainResult | null;
  blockExplorerUrl?: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function truncate(str: string | null | undefined, head = 8, tail = 6): string {
  if (!str) return "—";
  if (str.length <= head + tail + 3) return str;
  return `${str.slice(0, head)}…${str.slice(-tail)}`;
}

function formatTimestamp(iso?: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZoneName: "short",
    });
  } catch {
    return iso;
  }
}

// ── Sub-components ────────────────────────────────────────────────────────────

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select-all
    }
  };

  return (
    <button
      id="copy-sha256-btn"
      onClick={handleCopy}
      title="Copy full hash"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        padding: "3px 8px",
        borderRadius: "var(--radius-sm)",
        border: "1px solid var(--border)",
        background: copied ? "var(--emerald-50, #ecfdf5)" : "var(--bg-surface)",
        color: copied ? "var(--emerald-600, #059669)" : "var(--text-muted)",
        fontSize: "0.72rem",
        fontWeight: 600,
        cursor: "pointer",
        transition: "all 0.15s ease",
        flexShrink: 0,
        lineHeight: 1,
      }}
    >
      {copied ? (
        <>
          <CheckCheck size={11} />
          Copied
        </>
      ) : (
        <>
          <Copy size={11} />
          Copy
        </>
      )}
    </button>
  );
}

interface RowProps {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}

function DetailRow({ icon, label, value }: RowProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "10px",
        padding: "10px 12px",
        borderRadius: "var(--radius-sm)",
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
      }}
    >
      <div style={{ color: "var(--text-muted)", flexShrink: 0, marginTop: "1px" }}>
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p
          style={{
            margin: "0 0 3px",
            fontSize: "0.72rem",
            fontWeight: 600,
            color: "var(--text-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          {label}
        </p>
        <div
          style={{
            fontSize: "0.8rem",
            color: "var(--text-secondary)",
            fontFamily: "JetBrains Mono, monospace",
            wordBreak: "break-all",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            flexWrap: "wrap",
          }}
        >
          {value}
        </div>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function BlockchainCertificate({
  data,
  blockExplorerUrl = "https://amoy.polygonscan.com",
}: BlockchainCertificateProps) {
  const isSealed = data?.status === "sealed";
  const hasData = !!data;

  // ── Colour scheme based on status ────────────────────────────────────────
  const accent = isSealed
    ? { bg: "#f0fdf4", border: "#bbf7d0", icon: "#16a34a", text: "#15803d" }
    : { bg: "#fffbeb", border: "#fde68a", icon: "#d97706", text: "#b45309" };

  return (
    <div
      className="card animate-fade-in-up"
      style={{ padding: "0", overflow: "hidden", marginTop: "16px" }}
    >
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "12px",
          padding: "16px 20px",
          background: accent.bg,
          borderBottom: `1px solid ${accent.border}`,
        }}
      >
        {/* Icon */}
        <div
          style={{
            width: "38px",
            height: "38px",
            borderRadius: "var(--radius-md)",
            background: accent.border,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          {isSealed ? (
            <ShieldCheck size={20} color={accent.icon} strokeWidth={2.5} />
          ) : (
            <ShieldOff size={20} color={accent.icon} strokeWidth={2.5} />
          )}
        </div>

        {/* Title + badge */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              flexWrap: "wrap",
            }}
          >
            <h2
              style={{
                margin: 0,
                fontSize: "0.95rem",
                fontWeight: 800,
                color: "var(--text-primary)",
                letterSpacing: "-0.01em",
              }}
            >
              {isSealed ? "Cryptographically Sealed" : "Off-Chain Verification"}
            </h2>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                padding: "2px 8px",
                borderRadius: "999px",
                background: accent.border,
                color: accent.text,
                fontSize: "0.7rem",
                fontWeight: 700,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              <Blocks size={9} />
              {isSealed ? "Polygon Amoy" : "Local Hashes Only"}
            </span>
          </div>
          <p
            style={{
              margin: "3px 0 0",
              fontSize: "0.78rem",
              color: "var(--text-muted)",
            }}
          >
            {isSealed
              ? "This forensic report has been permanently sealed on the Polygon blockchain."
              : "Blockchain keys not configured — SHA-256 & pHash computed locally."}
          </p>
        </div>
      </div>

      {/* ── Details Grid ─────────────────────────────────────────────────── */}
      <div
        style={{
          padding: "16px 20px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
        }}
      >
        {/* Transaction Hash (only when sealed) */}
        {isSealed && data?.tx_hash && (
          <DetailRow
            icon={<ExternalLink size={14} />}
            label="Transaction Hash"
            value={
              <a
                id="blockchain-tx-link"
                href={`${blockExplorerUrl}/tx/${data.tx_hash}`}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: "var(--indigo-600)",
                  textDecoration: "none",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                }}
              >
                {truncate(data.tx_hash, 10, 8)}
                <ExternalLink size={11} />
              </a>
            }
          />
        )}

        {/* IPFS CID (only when pinned) */}
        {data?.ipfs_cid && (
          <DetailRow
            icon={<LinkIcon size={14} />}
            label="IPFS Decentralized CID"
            value={
              <a
                id="blockchain-ipfs-link"
                href={`https://gateway.pinata.cloud/ipfs/${data.ipfs_cid}`}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: "var(--indigo-600)",
                  textDecoration: "none",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                }}
              >
                {truncate(data.ipfs_cid, 12, 8)}
                <ExternalLink size={11} />
              </a>
            }
          />
        )}

        {/* SHA-256 */}
        <DetailRow
          icon={<Hash size={14} />}
          label="SHA-256 Checksum"
          value={
            data?.sha256 ? (
              <>
                <span id="blockchain-sha256-value">
                  {truncate(data.sha256, 16, 8)}
                </span>
                <CopyButton value={data.sha256} />
              </>
            ) : (
              <span style={{ color: "var(--text-muted)", fontStyle: "italic" }}>
                Not computed
              </span>
            )
          }
        />

        {/* Perceptual Hash */}
        <DetailRow
          icon={<Fingerprint size={14} />}
          label="Perceptual Hash (pHash)"
          value={
            <span id="blockchain-phash-value" style={{ color: "var(--text-secondary)" }}>
              {data?.phash || "—"}
            </span>
          }
        />

        {/* Timestamp */}
        {isSealed && (
          <DetailRow
            icon={<Clock size={14} />}
            label="Block Confirmation Timestamp"
            value={
              <span
                id="blockchain-timestamp-value"
                style={{
                  color: "var(--text-secondary)",
                  fontFamily: "inherit",
                  fontSize: "0.82rem",
                }}
              >
                {formatTimestamp(data?.timestamp)}
              </span>
            }
          />
        )}

        {/* No data fallback */}
        {!hasData && (
          <p
            style={{
              margin: 0,
              fontSize: "0.8rem",
              color: "var(--text-muted)",
              textAlign: "center",
              padding: "12px 0",
            }}
          >
            Provenance data not available for this job.
          </p>
        )}
      </div>

      {/* ── Footer note ──────────────────────────────────────────────────── */}
      <div
        style={{
          padding: "10px 20px",
          background: "var(--bg-subtle)",
          borderTop: "1px solid var(--border)",
        }}
      >
        <p
          style={{
            margin: 0,
            fontSize: "0.72rem",
            color: "var(--text-muted)",
            lineHeight: 1.5,
          }}
        >
          {isSealed
            ? `On-chain record is permanent and immutable. Verify at ${blockExplorerUrl}`
            : "Set WALLET_PRIVATE_KEY & CONTRACT_ADDRESS in backend/.env to enable on-chain sealing."}
        </p>
      </div>
    </div>
  );
}
