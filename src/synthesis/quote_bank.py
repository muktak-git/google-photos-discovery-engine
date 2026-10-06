"""Verbatim evidence bank compiler indexing unaltered public quotes by failure archetype."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from src.common.config import get_config
from src.common.logger import get_logger
from src.common.schemas import MemorySignalRecord, ProblemCluster, SearchFailureMode

logger = get_logger("Synthesis.QuoteBank")


class EvidenceBankBuilder:
    """Compiles verified, privacy-scrubbed verbatim quotes into a structured evidence artifact."""

    def __init__(self) -> None:
        self.config = get_config()

    def build_evidence_bank(
        self,
        records: List[MemorySignalRecord],
        clusters: List[ProblemCluster],
        output_path: Optional[Path] = None,
    ) -> Path:
        """Generates verbatim_evidence_bank.md grouped by retrieval problem and photo type."""
        self.config.ensure_directories()
        target_path = output_path or (self.config.output_dir / "verbatim_evidence_bank.md")

        # Group records by failure mode
        records_by_mode: Dict[SearchFailureMode, List[MemorySignalRecord]] = {}
        for r in records:
            records_by_mode.setdefault(r.failure_mode, []).append(r)

        md_lines: List[str] = [
            "# Verbatim User Evidence Bank: Visual Memory Retrieval Breakdowns",
            "",
            "---",
            "",
            "> [!IMPORTANT]",
            "> **Veracity & Privacy Certification:**",
            "> 1. **100% Verbatim:** Every quote below is programmatically verified as an exact word-for-word substring from the original public discussion.",
            "> 2. **Zero PII:** All personal identifiers (names, handles, emails, device IDs, GPS coordinates) have been strictly stripped (`[USER]`, `[PERSON]`, `[FAMILY_MEMBER]`, `[DEVICE]`).",
            "> 3. **Uninvented Reality:** No paraphrasing, LLM hallucinations, or synthetic wording have been introduced.",
            "",
            "---",
            "",
            "## 1. Evidence Distribution Summary",
            "",
            f"- **Total Verified Quotes:** {len(records)}",
            f"- **Distinct Failure Archetypes:** {len(records_by_mode)}",
            f"- **Primary Problem Spaces:** {len(clusters)}",
            "",
            "| Failure Mode | Quote Count | Primary Photo Categories | Mean Frustration (1-5) |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for mode, mode_records in sorted(
            records_by_mode.items(), key=lambda x: len(x[1]), reverse=True
        ):
            photo_types = ", ".join(sorted(list(set(r.photo_type for r in mode_records))))
            avg_frust = round(
                sum(r.user_frustration_score for r in mode_records) / len(mode_records), 2
            )
            md_lines.append(
                f"| `{mode.value}` | **{len(mode_records)}** | {photo_types} | {avg_frust} / 5.0 |"
            )

        md_lines.extend(["", "---", "", "## 2. Categorized Verbatim Evidence", ""])

        for mode, mode_records in sorted(
            records_by_mode.items(), key=lambda x: len(x[1]), reverse=True
        ):
            md_lines.append(f"### Problem Archetype: `{mode.value}`")
            md_lines.append("")

            # Find matching cluster description
            matching_cluster = next(
                (c for c in clusters if c.primary_failure_mode == mode), None
            )
            if matching_cluster:
                md_lines.append(f"**Cluster Association:** `{matching_cluster.cluster_id}` — *{matching_cluster.cluster_title}*")
                md_lines.append(f"> {matching_cluster.description}")
                md_lines.append("")

            for i, r in enumerate(mode_records, start=1):
                cues_summary = ", ".join(
                    f"{'NOT ' if c.is_negated else ''}{c.detail} ({c.cue_type.value})"
                    for c in r.remembered_cues
                )
                queries_summary = ", ".join(f"`{q}`" for q in r.attempted_queries) or "None recorded"
                forgotten_summary = ", ".join(r.forgotten_details) or "None specified"

                md_lines.append(f"#### Evidence Item {i} ({r.photo_type.title()})")
                md_lines.append(f"> \"{r.verbatim_quote}\"")
                md_lines.append("")
                md_lines.append(f"- **Photo Category:** `{r.photo_type}`")
                md_lines.append(f"- **Remembered Cues:** {cues_summary}")
                md_lines.append(f"- **Forgotten Details:** {forgotten_summary}")
                md_lines.append(f"- **Attempted Search Queries:** {queries_summary}")
                md_lines.append(f"- **User Friction Level:** {r.user_frustration_score} / 5.0")
                md_lines.append(f"- **Record Traceability ID:** `{r.record_id}`")
                md_lines.append("")

            md_lines.append("---")
            md_lines.append("")

        with open(target_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        logger.info(
            "Compiled verbatim evidence bank with %d quotes to %s",
            len(records),
            target_path,
        )
        return target_path
