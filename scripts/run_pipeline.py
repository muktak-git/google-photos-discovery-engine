"""Unified CLI entry point for the Photo Retrieval Discovery Engine."""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Dict, List, Optional

from src.common.config import get_config
from src.common.logger import get_logger, setup_logger
from src.common.schemas import PipelineCheckpoint
from src.clustering.pipeline import ClusteringPipeline
from src.extraction.pipeline import ExtractionPipeline
from src.filtering.pipeline import FilteringPipeline
from src.ingestion.pipeline import IngestionPipeline
from src.synthesis.pipeline import SynthesisPipeline

logger = get_logger("Runner")


class DiscoveryEngineRunner:
    """Orchestrates end-to-end pipeline execution with checkpointing and resume support."""

    def __init__(self) -> None:
        self.config = get_config()
        self.config.ensure_directories()
        self.checkpoint_path = self.config.data_dir / "checkpoint.json"

    def load_checkpoint(self) -> Optional[PipelineCheckpoint]:
        """Loads existing checkpoint if present."""
        if self.checkpoint_path.exists():
            try:
                with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                    return PipelineCheckpoint.model_validate(json.load(f))
            except Exception as e:
                logger.warning("Could not read checkpoint file: %s", str(e))
        return None

    def save_checkpoint(self, checkpoint: PipelineCheckpoint) -> None:
        """Saves current pipeline state to disk."""
        with open(self.checkpoint_path, "w", encoding="utf-8") as f:
            f.write(checkpoint.model_dump_json(indent=2))

    def run(
        self,
        sources: Optional[List[str]] = None,
        limit_per_source: int = 50,
        skip_ingestion: bool = False,
        resume: bool = False,
        export_reports: bool = True,
    ) -> Dict[str, Any]:
        """Executes pipeline across all 5 operational stages."""
        run_id = f"run_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        start_time = time.time()

        checkpoint = None
        if resume:
            checkpoint = self.load_checkpoint()
            if checkpoint:
                logger.info(
                    "Resuming run from checkpoint. Last completed stage: '%s'",
                    checkpoint.last_completed_stage,
                )

        if not checkpoint:
            checkpoint = PipelineCheckpoint(
                pipeline_run_id=run_id,
                started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )

        print("\n" + "=" * 80)
        print("   AI-POWERED PHOTO RETRIEVAL DISCOVERY ENGINE — PIPELINE EXECUTION")
        print("=" * 80 + "\n")

        # -------------------------------------------------------------
        # Stage 1: Ingestion & Privacy Sanitization
        # -------------------------------------------------------------
        if not skip_ingestion and (not resume or not checkpoint.last_completed_stage):
            print(">>> [Stage 1/5] Running Multi-Source Ingestion & PII Sanitization...")
            ingest_pipe = IngestionPipeline()
            ingest_res = ingest_pipe.run_ingestion(
                sources=sources, limit_per_source=limit_per_source
            )
            checkpoint.records_ingested = ingest_res["total_raw_records"]
            checkpoint.records_sanitized = ingest_res["total_sanitized_records"]
            checkpoint.metadata["low_info_spam_excluded"] = ingest_res.get("low_info_spam_excluded", 0)
            checkpoint.last_completed_stage = "Stage 1: Ingestion & Privacy Sanitization"
            self.save_checkpoint(checkpoint)
            print(
                f"    [Done] Ingested: {checkpoint.records_ingested} | Actual Useful Cleaned: {checkpoint.records_sanitized} (Excluded {ingest_res.get('low_info_spam_excluded', 0)} low-info spam/ratings)\n"
            )
        else:
            print(">>> [Stage 1/5] Ingestion skipped or loaded from prior checkpoint.\n")

        # -------------------------------------------------------------
        # Stage 2: Intent & Relevancy Filtering
        # -------------------------------------------------------------
        if not resume or checkpoint.last_completed_stage == "Stage 1: Ingestion & Privacy Sanitization":
            print(">>> [Stage 2/5] Running Two-Tier Relevancy & Intent Filter...")
            filter_pipe = FilteringPipeline()
            filter_res = filter_pipe.run_filtering()
            checkpoint.records_filtered = filter_res["relevant_retrieval_records"]
            checkpoint.last_completed_stage = "Stage 2: Relevancy Filtering"
            self.save_checkpoint(checkpoint)
            print(
                f"    [Done] Screened: {filter_res['total_processed']} | Relevant Struggles: {checkpoint.records_filtered} (Yield: {filter_res['yield_rate_percent']}%)\n"
            )
        else:
            print(">>> [Stage 2/5] Filtering already completed in checkpoint.\n")

        # -------------------------------------------------------------
        # Stage 3: Cognitive Signal Extraction
        # -------------------------------------------------------------
        if not resume or checkpoint.last_completed_stage == "Stage 2: Relevancy Filtering":
            print(">>> [Stage 3/5] Extracting Cognitive Signals & Verifying Verbatim Quotes...")
            extract_pipe = ExtractionPipeline()
            extract_res = extract_pipe.run_extraction()
            checkpoint.records_extracted = extract_res["total_extracted"]
            checkpoint.last_completed_stage = "Stage 3: Cognitive Signal Extraction"
            self.save_checkpoint(checkpoint)
            print(
                f"    [Done] Extracted: {checkpoint.records_extracted} | Quote Verification Rate: {extract_res['quote_verification_pass_rate']}%\n"
            )
        else:
            print(">>> [Stage 3/5] Cognitive signal extraction completed in checkpoint.\n")

        # -------------------------------------------------------------
        # Stage 4: Semantic Clustering & Problem Taxonomy
        # -------------------------------------------------------------
        if not resume or checkpoint.last_completed_stage == "Stage 3: Cognitive Signal Extraction":
            print(">>> [Stage 4/5] Running Semantic Clustering & Problem Map Modeling...")
            cluster_pipe = ClusteringPipeline()
            cluster_res = cluster_pipe.run_clustering()
            checkpoint.clusters_identified = cluster_res["clusters_formed"]
            checkpoint.last_completed_stage = "Stage 4: Problem Clustering"
            self.save_checkpoint(checkpoint)
            print(
                f"    [Done] Formed: {checkpoint.clusters_identified} distinct problem clusters\n"
            )
        else:
            print(">>> [Stage 4/5] Clustering completed in checkpoint.\n")

        # -------------------------------------------------------------
        # Stage 5: Opportunity Scoring & Synthesis
        # -------------------------------------------------------------
        print(">>> [Stage 5/5] Synthesizing Opportunity Matrix & Compiling Deliverables...")
        synth_pipe = SynthesisPipeline()
        synth_res = synth_pipe.run_synthesis()
        checkpoint.is_complete = True
        checkpoint.last_completed_stage = "Stage 5: Synthesis & Reporting Complete"
        self.save_checkpoint(checkpoint)
        print("    [Done] Synthesis complete.\n")

        total_elapsed = round(time.time() - start_time, 2)

        # Print Executive Summary Banner
        self._print_executive_summary(synth_res, total_elapsed)
        return synth_res

    def _print_executive_summary(self, synth_res: Dict[str, Any], elapsed_seconds: float) -> None:
        """Prints a human-readable executive dashboard in the console."""
        primary = synth_res.get("primary_recommendation", {})
        delivs = synth_res.get("deliverables_generated", {})

        print("\n" + "=" * 80)
        print("                     EXECUTIVE DISCOVERY DASHBOARD")
        print("=" * 80)
        print(f"Total Execution Time:      {elapsed_seconds}s")
        print(f"Total Signals Indexed:     {synth_res.get('total_signals_indexed')}")
        print(f"Problem Clusters Formed:   {synth_res.get('total_clusters_analyzed')}")
        print(f"Opportunities Evaluated:   {synth_res.get('opportunities_evaluated')}")
        print("-" * 80)
        print(f"PRIMARY RECOMMENDATION:    {primary.get('title')}")
        print(f"Composite Score:           {primary.get('composite_score')} / 5.00")
        print("-" * 80)
        print("DELIVERABLES GENERATED:")
        print(f"  1. Retrieval Problem Map:    {delivs.get('retrieval_problem_map')}")
        print(f"  2. Verbatim Evidence Bank:   {delivs.get('verbatim_evidence_bank')}")
        print(f"  3. Opportunity Analysis:     {delivs.get('opportunity_analysis')}")
        print("=" * 80 + "\n")


def main() -> None:
    """CLI argument parser and main execution function."""
    parser = argparse.ArgumentParser(
        description="AI-Powered Photo Retrieval Discovery Engine CLI"
    )
    parser.add_argument(
        "--sources",
        type=str,
        default="all",
        help="Comma-separated sources: play_store,app_store,reddit,community_forum,youtube or 'all'",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Maximum records to ingest per source",
    )
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="Skip ingestion and run from existing sanitized data lake",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume pipeline from the last saved stage checkpoint",
    )
    parser.add_argument(
        "--export-reports",
        action="store_true",
        default=True,
        help="Export markdown and JSON deliverable reports",
    )

    args = parser.parse_args()

    # Parse sources
    target_sources = None
    if args.sources.lower() != "all":
        target_sources = [s.strip() for s in args.sources.split(",") if s.strip()]

    runner = DiscoveryEngineRunner()
    runner.run(
        sources=target_sources,
        limit_per_source=args.limit,
        skip_ingestion=args.skip_ingestion,
        resume=args.resume,
        export_reports=args.export_reports,
    )


if __name__ == "__main__":
    main()
