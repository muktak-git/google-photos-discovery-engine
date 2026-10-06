"""Synthesis pipeline coordinator for deliverables compilation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.common.config import get_config
from src.common.logger import get_logger
from src.common.schemas import MemorySignalRecord, ProblemCluster
from src.synthesis.quote_bank import EvidenceBankBuilder
from src.synthesis.ranking import OpportunityRanker
from src.synthesis.report_generator import ReportGenerator

logger = get_logger("Synthesis.Pipeline")


class SynthesisPipeline:
    """Coordinates opportunity scoring, verbatim evidence indexing, and final artifact generation."""

    def __init__(self) -> None:
        self.config = get_config()
        self.ranker = OpportunityRanker()
        self.evidence_builder = EvidenceBankBuilder()
        self.report_generator = ReportGenerator()

    def run_synthesis(
        self,
        signals_input_path: Optional[Path] = None,
        problem_map_input_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Loads signals and clusters, ranks opportunities, and generates all final deliverables."""
        self.config.ensure_directories()

        signals_file = (
            signals_input_path or (self.config.extracted_dir / "signals.jsonl")
        )
        problem_map_file = (
            problem_map_input_path
            or (self.config.output_dir / "retrieval_problem_map.json")
        )

        if not signals_file.exists():
            raise FileNotFoundError(f"Signals file not found: {signals_file}")
        if not problem_map_file.exists():
            raise FileNotFoundError(f"Problem map file not found: {problem_map_file}")

        # Load signals
        records: List[MemorySignalRecord] = []
        with open(signals_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(MemorySignalRecord.model_validate(json.loads(line)))

        # Load clusters
        with open(problem_map_file, "r", encoding="utf-8") as f:
            pmap_data = json.load(f)
            clusters = [ProblemCluster.model_validate(c) for c in pmap_data.get("clusters", [])]

        # 1. Rank Opportunities
        ranked_opps = self.ranker.rank_opportunities(clusters, records)

        # 2. Compile Verbatim Evidence Bank
        evidence_bank_path = self.evidence_builder.build_evidence_bank(records, clusters)

        # 3. Generate Executive Opportunity Analysis Report
        report_path = self.report_generator.generate_report(clusters, ranked_opps, records)

        primary_opp = next((o for o in ranked_opps if o.is_primary_recommendation), None)

        summary = {
            "total_signals_indexed": len(records),
            "total_clusters_analyzed": len(clusters),
            "opportunities_evaluated": len(ranked_opps),
            "primary_recommendation": {
                "id": primary_opp.opportunity_id if primary_opp else "None",
                "title": primary_opp.opportunity_title if primary_opp else "None",
                "composite_score": primary_opp.composite_score if primary_opp else 0.0,
            },
            "deliverables_generated": {
                "retrieval_problem_map": str(problem_map_file),
                "verbatim_evidence_bank": str(evidence_bank_path),
                "opportunity_analysis": str(report_path),
            },
        }

        logger.info(
            "Phase 5 Synthesis Complete. Primary opportunity: '%s' (Score: %.2f)",
            primary_opp.opportunity_title if primary_opp else "None",
            primary_opp.composite_score if primary_opp else 0.0,
        )
        return summary
