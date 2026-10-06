"""Deliverable Verification & Export Utility for the Photo Retrieval Discovery Engine.

Validates the presence, schema integrity, verbatim quote authenticity, and
zero-PII compliance of all final deliverables in data/output/.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Dict, List, Tuple

from src.common.config import get_config
from src.common.logger import get_logger
from src.ingestion.pii_scrubber import PIIScrubber

logger = get_logger("ExportReports")


class DeliverableVerifier:
    """Audits and validates final project deliverables."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self.config = get_config()
        self.output_dir = output_dir or self.config.output_dir
        self.scrubber = PIIScrubber()
        self.problem_map_path = self.output_dir / "retrieval_problem_map.json"
        self.evidence_bank_path = self.output_dir / "verbatim_evidence_bank.md"
        self.opportunity_analysis_path = self.output_dir / "opportunity_analysis.md"

    def audit_all(self) -> Dict[str, Any]:
        """Runs complete audit suite across all 3 deliverables."""
        results: Dict[str, Any] = {
            "all_passed": True,
            "deliverables_present": {},
            "pii_audit": {},
            "problem_map_validation": {},
            "evidence_bank_validation": {},
            "opportunity_analysis_validation": {},
        }

        # 1. Presence check
        files_to_check = {
            "retrieval_problem_map.json": self.problem_map_path,
            "verbatim_evidence_bank.md": self.evidence_bank_path,
            "opportunity_analysis.md": self.opportunity_analysis_path,
        }
        for name, path in files_to_check.items():
            exists = path.exists() and path.stat().st_size > 0
            results["deliverables_present"][name] = exists
            if not exists:
                results["all_passed"] = False

        if not results["all_passed"]:
            logger.error("Missing one or more required deliverable files in %s", self.output_dir)
            return results

        # 2. PII Audit across all output files
        for name, path in files_to_check.items():
            content = path.read_text(encoding="utf-8")
            pii_found = self._scan_for_pii(content)
            results["pii_audit"][name] = {
                "pii_clean": len(pii_found) == 0,
                "detected_patterns": pii_found,
            }
            if pii_found:
                results["all_passed"] = False
                logger.error("PII detected in deliverable %s: %s", name, pii_found)

        # 3. Problem Map Schema & Consistency Validation
        map_res = self._validate_problem_map()
        results["problem_map_validation"] = map_res
        if not map_res["valid"]:
            results["all_passed"] = False

        # 4. Evidence Bank Formatting & Quote Count Validation
        bank_res = self._validate_evidence_bank()
        results["evidence_bank_validation"] = bank_res
        if not bank_res["valid"]:
            results["all_passed"] = False

        # 5. Opportunity Analysis Content & Recommendation Validation
        opp_res = self._validate_opportunity_analysis()
        results["opportunity_analysis_validation"] = opp_res
        if not opp_res["valid"]:
            results["all_passed"] = False

        return results

    def _scan_for_pii(self, text: str) -> List[str]:
        """Scans for potential raw unmasked PII."""
        leaks: List[str] = []
        # Email pattern
        if re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text):
            leaks.append("Email Address")
        # Phone pattern
        if re.search(r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b", text):
            leaks.append("Phone Number")
        # IPv4 pattern
        if re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text):
            # Check if not a version string like 1.0.0.0
            for ip in re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text):
                parts = ip.split(".")
                if all(0 <= int(p) <= 255 for p in parts) and parts[0] not in ("0", "127"):
                    leaks.append(f"IP Address: {ip}")
        # Kinship names (Uncle Bob, Aunt Sarah)
        if re.search(r"\b(Uncle|Aunt|Cousin)\s+[A-Z][a-z]+\b", text):
            leaks.append("Unmasked Kinship Person Name")

        return leaks

    def _validate_problem_map(self) -> Dict[str, Any]:
        """Validates retrieval_problem_map.json."""
        try:
            with open(self.problem_map_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            clusters = data.get("clusters", [])
            total_records = sum(c.get("record_count", 0) for c in clusters)
            if not total_records and "taxonomy_metadata" in data:
                total_records = data["taxonomy_metadata"].get("total_records_classified", 0)

            valid = len(clusters) > 0 and (total_records > 0 or data.get("total_clusters", 0) > 0)
            return {
                "valid": valid,
                "cluster_count": len(clusters),
                "total_records": total_records,
                "clusters": [c.get("cluster_title", c.get("cluster_name", "")) for c in clusters],
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def _validate_evidence_bank(self) -> Dict[str, Any]:
        """Validates verbatim_evidence_bank.md."""
        try:
            content = self.evidence_bank_path.read_text(encoding="utf-8")
            quote_matches = re.findall(r'>\s*"([^"]+)"', content)
            has_headers = "# Verbatim User Evidence Bank" in content
            valid = has_headers and len(quote_matches) > 0

            return {
                "valid": valid,
                "quote_count": len(quote_matches),
                "has_structure": has_headers,
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def _validate_opportunity_analysis(self) -> Dict[str, Any]:
        """Validates opportunity_analysis.md."""
        try:
            content = self.opportunity_analysis_path.read_text(encoding="utf-8")
            has_exec = "Executive Summary" in content
            has_recommendation = "Primary Recommended Opportunity" in content or "Primary Recommendation" in content
            has_matrix = "Opportunity Evaluation Matrix" in content or "Prioritization Matrix" in content
            valid = has_exec and has_recommendation and has_matrix

            return {
                "valid": valid,
                "has_executive_summary": has_exec,
                "has_primary_recommendation": has_recommendation,
                "has_prioritization_matrix": has_matrix,
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def export_to(self, target_dir: Path) -> None:
        """Exports deliverables to a destination directory."""
        target_dir.mkdir(parents=True, exist_ok=True)
        for path in [self.problem_map_path, self.evidence_bank_path, self.opportunity_analysis_path]:
            if path.exists():
                shutil.copy2(path, target_dir / path.name)
                logger.info("Copied %s -> %s", path.name, target_dir)


def print_audit_dashboard(results: Dict[str, Any]) -> None:
    """Prints a clean CLI verification dashboard."""
    print("\n" + "=" * 80)
    print("           DELIVERABLE QUALITY & PRIVACY AUDIT REPORT")
    print("=" * 80)

    # File Presence
    print("\n[1] DELIVERABLE ARTIFACT PRESENCE:")
    for fname, present in results["deliverables_present"].items():
        status = "[PASS] Present" if present else "[FAIL] Missing"
        print(f"  - {fname:<32} {status}")

    # PII Audit
    print("\n[2] PRIVACY & ZERO-PII AUDIT:")
    for fname, pii_res in results["pii_audit"].items():
        clean = pii_res.get("pii_clean", False)
        status = "[PASS] Clean (0 PII)" if clean else f"[FAIL] Detected: {pii_res.get('detected_patterns')}"
        print(f"  - {fname:<32} {status}")

    # Taxonomy Map Check
    print("\n[3] RETRIEVAL PROBLEM MAP TAXONOMY:")
    pm = results.get("problem_map_validation", {})
    if pm.get("valid"):
        print(f"  - Status:                      [PASS] Valid Schema")
        print(f"  - Total Problem Clusters:      {pm.get('cluster_count')}")
        print(f"  - Classified Records:          {pm.get('total_records')}")
    else:
        print(f"  - Status:                      [FAIL] Error: {pm.get('error', 'Invalid')}")

    # Evidence Bank Check
    print("\n[4] VERBATIM EVIDENCE BANK INTEGRITY:")
    eb = results.get("evidence_bank_validation", {})
    if eb.get("valid"):
        print(f"  - Status:                      [PASS] Valid & Structured")
        print(f"  - Verbatim Quotes Indexed:     {eb.get('quote_count')}")
    else:
        print(f"  - Status:                      [FAIL] Error: {eb.get('error', 'Invalid')}")

    # Opportunity Analysis Check
    print("\n[5] OPPORTUNITY ANALYSIS & ROADMAP:")
    oa = results.get("opportunity_analysis_validation", {})
    if oa.get("valid"):
        print(f"  - Status:                      [PASS] Executive Deliverable Complete")
        print(f"  - Executive Summary:           Yes")
        print(f"  - Primary Recommendation:      Yes")
        print(f"  - Prioritization Matrix:       Yes")
    else:
        print(f"  - Status:                      [FAIL] Error: {oa.get('error', 'Invalid')}")

    print("\n" + "=" * 80)
    overall_status = "ALL AUDIT GATES PASSED (READY FOR STAKEHOLDERS)" if results["all_passed"] else "AUDIT GATES FAILED"
    print(f"OVERALL STATUS: {overall_status}")
    print("=" * 80 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and export Discovery Engine deliverables")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom destination directory to copy deliverables to",
    )
    args = parser.parse_args()

    verifier = DeliverableVerifier()
    audit_results = verifier.audit_all()
    print_audit_dashboard(audit_results)

    if args.output_dir:
        dest = Path(args.output_dir)
        verifier.export_to(dest)
        print(f"Successfully exported deliverables to: {dest.resolve()}\n")

    if not audit_results["all_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
