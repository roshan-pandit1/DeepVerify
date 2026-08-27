"""
Source & Network Credibility Layer

Computes source trust metrics and propagation anomaly signals:
- Account trust score (age, verification status, historical policy violations)
- Propagation anomaly score (z-score of share velocity vs platform baseline, bot-like burst patterns)
"""

from typing import Dict, Any, List, Optional
import math
import os
import yaml


class SourceNetworkAnalyzer:
    """Evaluates source trust and engagement/propagation velocity anomalies."""

    def __init__(self, config_path: Optional[str] = None):
        self.weight_account_age = 0.35
        self.weight_verification = 0.25
        self.weight_violation_history = 0.40
        self.baseline_share_velocity = 10.0  # shares per minute
        self.share_velocity_std_dev = 5.0

        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                if cfg and "source_network_params" in cfg:
                    p = cfg["source_network_params"]
                    self.weight_account_age = p.get("weight_account_age", 0.35)
                    self.weight_verification = p.get("weight_verification", 0.25)
                    self.weight_violation_history = p.get("weight_violation_history", 0.40)
                    self.baseline_share_velocity = p.get("baseline_share_velocity", 10.0)
                    self.share_velocity_std_dev = p.get("share_velocity_std_dev", 5.0)

    def compute_account_trust(
        self,
        account_age_days: int,
        is_verified: bool,
        historical_violation_count: int,
    ) -> float:
        """
        Calculates account trust score (0.0 to 1.0).
        Older accounts, verified badges, and zero violations increase trust.
        """
        # Account age factor (capped at 1 year / 365 days)
        age_factor = min(1.0, max(0.0, account_age_days / 365.0))

        # Verification status
        verification_factor = 1.0 if is_verified else 0.5

        # Violation history penalty (each violation reduces score by 0.25)
        violation_factor = max(0.0, 1.0 - (0.25 * max(0, historical_violation_count)))

        trust_score = (
            (self.weight_account_age * age_factor)
            + (self.weight_verification * verification_factor)
            + (self.weight_violation_history * violation_factor)
        )

        return min(1.0, max(0.0, trust_score))

    def compute_propagation_anomaly(
        self,
        share_velocity: float,
        new_account_share_ratio: float = 0.0,
        share_timestamps: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """
        Calculates propagation anomaly score (0.0 to 1.0).
        High z-score velocity and high share ratio from new accounts signal bot bursts.
        """
        std_dev = max(0.1, self.share_velocity_std_dev)
        z_score = (share_velocity - self.baseline_share_velocity) / std_dev

        # Normalize z_score anomaly (z_score >= 4.0 corresponds to max anomaly)
        z_anomaly = max(0.0, min(1.0, z_score / 4.0)) if z_score > 0 else 0.0

        # Bot coordination bonus (e.g. >30% of shares come from brand-new accounts)
        bot_coordination_penalty = 0.0
        if new_account_share_ratio > 0.5:
            bot_coordination_penalty = 0.3
        elif new_account_share_ratio > 0.3:
            bot_coordination_penalty = 0.15

        # Micro-burst detection from timestamp clustering if provided
        burst_detected = False
        if share_timestamps and len(share_timestamps) >= 5:
            # Check if 5+ shares occurred within a 10-second window
            sorted_ts = sorted(share_timestamps)
            for i in range(len(sorted_ts) - 4):
                if sorted_ts[i + 4] - sorted_ts[i] <= 10.0:
                    burst_detected = True
                    break

        if burst_detected:
            bot_coordination_penalty += 0.2

        total_anomaly = min(1.0, z_anomaly + bot_coordination_penalty)

        reasons = []
        if z_score > 2.0:
            reasons.append(f"Abnormal share velocity (z-score: {z_score:.2f})")
        if new_account_share_ratio > 0.3:
            reasons.append(f"High share ratio from new accounts ({new_account_share_ratio*100:.1f}%)")
        if burst_detected:
            reasons.append("Micro-burst pattern detected (>=5 shares in 10s window)")

        return {
            "propagation_anomaly_score": round(float(total_anomaly), 3),
            "z_score": round(float(z_score), 2),
            "burst_detected": burst_detected,
            "anomaly_reasons": reasons,
        }

    def analyze(
        self,
        account_age_days: int = 365,
        is_verified: bool = False,
        historical_violation_count: int = 0,
        share_velocity: float = 10.0,
        new_account_share_ratio: float = 0.0,
        share_timestamps: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """
        Combines account trust and propagation metrics into a unified Source Credibility Score (0.0 to 1.0).
        """
        account_trust = self.compute_account_trust(
            account_age_days=account_age_days,
            is_verified=is_verified,
            historical_violation_count=historical_violation_count,
        )

        anomaly_res = self.compute_propagation_anomaly(
            share_velocity=share_velocity,
            new_account_share_ratio=new_account_share_ratio,
            share_timestamps=share_timestamps,
        )
        anomaly_score = anomaly_res["propagation_anomaly_score"]

        # High trust + low anomaly = High overall source credibility
        # High anomaly reduces credibility score
        net_credibility = account_trust * (1.0 - (0.7 * anomaly_score))
        source_credibility_score = max(0.0, min(1.0, net_credibility))

        return {
            "source_credibility_score": round(float(source_credibility_score), 3),
            "account_trust_score": round(float(account_trust), 3),
            "propagation_anomaly_score": round(float(anomaly_score), 3),
            "z_score": anomaly_res["z_score"],
            "anomaly_reasons": anomaly_res["anomaly_reasons"],
        }
