"""End-to-End QA Pipeline Integration Test Suite."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.export_reports import DeliverableVerifier
from scripts.run_pipeline import DiscoveryEngineRunner
from src.common.config import get_config
from src.common.schemas import PipelineCheckpoint


class TestE2EPipeline(unittest.TestCase):
    """End-to-end integration tests for DiscoveryEngineRunner."""

    def setUp(self) -> None:
        self.config = get_config()
        self.runner = DiscoveryEngineRunner()

    def test_checkpoint_lifecycle(self) -> None:
        """Test checkpoint initialization, saving, loading, and stage updates."""
        test_checkpoint = PipelineCheckpoint(
            pipeline_run_id="test_run_001",
            started_at="2026-10-06T12:00:00Z",
            last_completed_stage="Stage 1: Ingestion & Privacy Sanitization",
            records_ingested=10,
            records_sanitized=10,
            records_filtered=5,
            records_extracted=4,
            clusters_identified=2,
            is_complete=False,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / "test_checkpoint.json"
            with patch.object(self.runner, "checkpoint_path", temp_path):
                self.assertIsNone(self.runner.load_checkpoint())

                self.runner.save_checkpoint(test_checkpoint)
                self.assertTrue(temp_path.exists())

                loaded = self.runner.load_checkpoint()
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded.pipeline_run_id, "test_run_001")
                self.assertEqual(loaded.records_ingested, 10)
                self.assertEqual(loaded.last_completed_stage, "Stage 1: Ingestion & Privacy Sanitization")
                self.assertFalse(loaded.is_complete)

    def test_runner_execution_flow(self) -> None:
        """Test complete runner pipeline flow with mock stages."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_checkpoint = Path(tmp_dir) / "checkpoint.json"

            with patch.object(self.runner, "checkpoint_path", temp_checkpoint):
                # Run with skip_ingestion=False, mocking individual stage pipelines
                with patch("scripts.run_pipeline.IngestionPipeline") as mock_ingest_cls, \
                     patch("scripts.run_pipeline.FilteringPipeline") as mock_filter_cls, \
                     patch("scripts.run_pipeline.ExtractionPipeline") as mock_extract_cls, \
                     patch("scripts.run_pipeline.ClusteringPipeline") as mock_cluster_cls, \
                     patch("scripts.run_pipeline.SynthesisPipeline") as mock_synth_cls:

                    # Configure mocks
                    mock_ingest = mock_ingest_cls.return_value
                    mock_ingest.run_ingestion.return_value = {
                        "total_raw_records": 50,
                        "total_sanitized_records": 50,
                    }

                    mock_filter = mock_filter_cls.return_value
                    mock_filter.run_filtering.return_value = {
                        "total_processed": 50,
                        "relevant_retrieval_records": 20,
                        "yield_rate_percent": 40.0,
                    }

                    mock_extract = mock_extract_cls.return_value
                    mock_extract.run_extraction.return_value = {
                        "total_extracted": 18,
                        "quote_verification_pass_rate": 100.0,
                    }

                    mock_cluster = mock_cluster_cls.return_value
                    mock_cluster.run_clustering.return_value = {
                        "clusters_formed": 4,
                    }

                    mock_synth = mock_synth_cls.return_value
                    mock_synth.run_synthesis.return_value = {
                        "status": "success",
                        "total_signals_indexed": 18,
                        "total_clusters_analyzed": 4,
                        "opportunities_evaluated": 4,
                        "primary_recommendation": {
                            "title": "Multi-Modal Visual Cue Retrieval",
                            "composite_score": 4.45,
                        },
                        "deliverables_generated": {
                            "retrieval_problem_map": "data/output/retrieval_problem_map.json",
                            "verbatim_evidence_bank": "data/output/verbatim_evidence_bank.md",
                            "opportunity_analysis": "data/output/opportunity_analysis.md",
                        },
                    }

                    # Execute pipeline
                    result = self.runner.run(
                        sources=["play_store"],
                        limit_per_source=10,
                        skip_ingestion=False,
                        resume=False,
                    )

                    # Verify stages were invoked
                    mock_ingest.run_ingestion.assert_called_once()
                    mock_filter.run_filtering.assert_called_once()
                    mock_extract.run_extraction.assert_called_once()
                    mock_cluster.run_clustering.assert_called_once()
                    mock_synth.run_synthesis.assert_called_once()

                    # Verify final results
                    self.assertEqual(result["status"], "success")
                    self.assertEqual(result["primary_recommendation"]["composite_score"], 4.45)

                    # Verify checkpoint was marked complete
                    final_checkpoint = self.runner.load_checkpoint()
                    self.assertIsNotNone(final_checkpoint)
                    self.assertTrue(final_checkpoint.is_complete)
                    self.assertEqual(final_checkpoint.records_ingested, 50)
                    self.assertEqual(final_checkpoint.records_filtered, 20)
                    self.assertEqual(final_checkpoint.records_extracted, 18)
                    self.assertEqual(final_checkpoint.clusters_identified, 4)

    def test_deliverable_verifier_audit(self) -> None:
        """Test that DeliverableVerifier passes on generated deliverables."""
        verifier = DeliverableVerifier()
        audit = verifier.audit_all()
        self.assertTrue(audit["all_passed"], f"Audit failed: {audit}")
        self.assertTrue(audit["deliverables_present"]["retrieval_problem_map.json"])
        self.assertTrue(audit["deliverables_present"]["verbatim_evidence_bank.md"])
        self.assertTrue(audit["deliverables_present"]["opportunity_analysis.md"])
        self.assertTrue(audit["pii_audit"]["retrieval_problem_map.json"]["pii_clean"])
        self.assertTrue(audit["pii_audit"]["verbatim_evidence_bank.md"]["pii_clean"])
        self.assertTrue(audit["pii_audit"]["opportunity_analysis.md"]["pii_clean"])


if __name__ == "__main__":
    unittest.main()
