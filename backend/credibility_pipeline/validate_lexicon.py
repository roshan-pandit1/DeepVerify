"""
Lexicon False-Positive Validation Suite

Audits the Lexicon Layer against a corpus of known-legitimate transcripts (news, academic, comedy, neutral commentary).
Measures per-category false-positive rates to ensure term lists are not overly broad before integrating into the ensemble.
"""

from typing import Dict, Any, List
import argparse
import os
import glob

from lexicon import LexiconAnalyzer


def run_false_positive_audit(
    data_dir: str,
    config_path: str = None,
    max_fp_threshold: float = 0.05,
) -> Dict[str, Any]:
    """
    Runs Lexicon Layer against all text files in data_dir and reports false-positive statistics.
    """
    analyzer = LexiconAnalyzer(config_path=config_path)

    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    text_files = glob.glob(os.path.join(data_dir, "*.txt"))
    if not text_files:
        print(f"Warning: No .txt files found in {data_dir}")
        return {
            "total_files": 0,
            "category_flag_rates": {},
            "warnings": [f"No .txt files found in {data_dir}"],
        }

    category_triggers = {cat: 0 for cat in analyzer.categories.keys()}
    density_scores = []

    for filepath in text_files:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        result = analyzer.analyze(text)
        density_scores.append(result["density_score"])

        for cat in result["categories_triggered"]:
            category_triggers[cat] += 1

    total_files = len(text_files)
    flag_rates = {
        cat: count / total_files for cat, count in category_triggers.items()
    }

    warnings = []
    for cat, rate in flag_rates.items():
        if rate > max_fp_threshold:
            warnings.append(
                f"ALERT: Category '{cat}' triggered on {rate*100:.1f}% of legitimate files "
                f"(exceeds target max FP threshold of {max_fp_threshold*100:.1f}%). Term list needs narrowing!"
            )

    avg_density = sum(density_scores) / total_files if total_files > 0 else 0.0

    report = {
        "total_files_audited": total_files,
        "average_density_score": round(avg_density, 3),
        "max_density_score": max(density_scores) if density_scores else 0.0,
        "category_flag_rates": {
            cat: f"{rate*100:.1f}% ({category_triggers[cat]}/{total_files})"
            for cat, rate in flag_rates.items()
        },
        "raw_rates": flag_rates,
        "warnings": warnings,
        "audit_passed": len(warnings) == 0,
    }

    return report


def print_report(report: Dict[str, Any]):
    print("\n==========================================================")
    print("      Lexicon Layer False-Positive Audit Report          ")
    print("==========================================================")
    print(f"Total Legitimate Files Audited: {report['total_files_audited']}")
    print(f"Average Density Score:         {report['average_density_score']}")
    print(f"Max Density Score:             {report['max_density_score']}")
    print("----------------------------------------------------------")
    print("Per-Category Trigger Rates on Legitimate Corpus:")
    for cat, rate_str in report["category_flag_rates"].items():
        print(f"  - {cat:20s}: {rate_str}")

    print("----------------------------------------------------------")
    if report["warnings"]:
        print("AUDIT WARNINGS:")
        for w in report["warnings"]:
            print(f"  [!] {w}")
    else:
        print("AUDIT PASSED: All categories are below the false-positive threshold.")
    print("==========================================================\n")


def main():
    parser = argparse.ArgumentParser(
        description="Audit Lexicon Layer against legitimate sample transcripts."
    )
    default_samples = os.path.join(os.path.dirname(__file__), "samples", "legitimate")
    if not os.path.exists(default_samples):
        default_samples = os.path.join(os.path.dirname(__file__), "samples")

    parser.add_argument(
        "--data-dir",
        type=str,
        default=default_samples,
        help="Path to folder containing legitimate transcript .txt files",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom config.yaml",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.05,
        help="Max acceptable false-positive rate per category (default: 0.05 / 5%%)",
    )

    args = parser.parse_args()

    report = run_false_positive_audit(
        data_dir=args.data_dir,
        config_path=args.config,
        max_fp_threshold=args.threshold,
    )
    print_report(report)


if __name__ == "__main__":
    main()
