"use client";

import Link from "next/link";
import { ShieldCheck, Search } from "lucide-react";

interface DeepVerifyLogoProps {
  className?: string;
  size?: "sm" | "md" | "lg";
}

export function DeepVerifyLogo({ className = "", size = "md" }: DeepVerifyLogoProps) {
  const iconSizes = {
    sm: 16,
    md: 18,
    lg: 22,
  };

  const textSizes = {
    sm: "0.9rem",
    md: "1.05rem",
    lg: "1.35rem",
  };

  const paddings = {
    sm: "5px 10px",
    md: "6px 14px",
    lg: "8px 18px",
  };

  return (
    <Link
      href="/"
      className={`deepverify-logo-box ${className}`}
      style={{ padding: paddings[size], textDecoration: "none" }}
    >
      {/* Animated Light Beam Scanner (Left-to-Right on Hover) */}
      <div className="deepverify-logo-scanner" />

      {/* Icon Mark with Sky Blue Accent */}
      <div className="deepverify-logo-icon">
        <ShieldCheck size={iconSizes[size]} />
      </div>

      {/* Brand Name Text: Black (Contrast White on Dark Semi-Box) + Sky Blue */}
      <span className="deepverify-logo-text" style={{ fontSize: textSizes[size] }}>
        <span className="deepverify-text-deep">Deep</span>
        <span className="deepverify-text-verify">Verify</span>
      </span>
    </Link>
  );
}

export default DeepVerifyLogo;
