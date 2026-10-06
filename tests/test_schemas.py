"""Unit tests for Pydantic data schemas in src/common/schemas.py."""

import unittest
from pydantic import ValidationError

from src.common.schemas import (
    FilteredConversationRecord,
    MemoryCueType,
    MemorySignalRecord,
    OpportunityRanking,
    PipelineCheckpoint,
    ProblemCluster,
    RawConversationRecord,
    RelevanceBucket,
    RememberedCue,
    SanitizedConversationRecord,
    SearchFailureMode,
)


class TestSchemas(unittest.TestCase):
    """Test suite covering data contract validation, scoring, and serialization."""

    def test_raw_conversation_record(self):
        """Verify raw conversation record creation and serialization."""
        record = RawConversationRecord(
            raw_id="raw_123",
            source="play_store",
            timestamp="2026-05-12T10:00:00Z",
            raw_text="Can't find my old yellow jacket picture from 2019",
            source_url="https://play.google.com/store/apps/details?id=sample",
            metadata={"rating": 2},
        )
        self.assertEqual(record.raw_id, "raw_123")
        self.assertEqual(record.source, "play_store")
        self.assertEqual(record.metadata["rating"], 2)

        # Verify min length constraint
        with self.assertRaises(ValidationError):
            RawConversationRecord(
                raw_id="raw_124",
                source="play_store",
                timestamp="2026-05-12",
                raw_text="",
            )

    def test_sanitized_conversation_record(self):
        """Verify sanitized record creation with PII tracking."""
        record = SanitizedConversationRecord(
            record_id="rec_001",
            raw_id="raw_123",
            source="play_store",
            timestamp="2026-05-12T10:00:00Z",
            sanitized_text="Can't find my old yellow jacket photo [USER]",
            pii_detected=["PERSON"],
        )
        self.assertEqual(record.record_id, "rec_001")
        self.assertIn("PERSON", record.pii_detected)
        self.assertIn("[USER]", record.sanitized_text)

    def test_filtered_conversation_record(self):
        """Verify relevancy categorization and helper properties."""
        rel_rec = FilteredConversationRecord(
            record_id="rec_001",
            source="play_store",
            timestamp="2026-05-12T10:00:00Z",
            sanitized_text="Looking for a photo I vaguely remember",
            relevance_bucket=RelevanceBucket.RELEVANT_PARTIAL_MEMORY,
            relevance_score=0.92,
        )
        self.assertTrue(rel_rec.is_relevant)

        noise_rec = FilteredConversationRecord(
            record_id="rec_002",
            source="play_store",
            timestamp="2026-05-12T10:00:00Z",
            sanitized_text="App crashed when opening settings",
            relevance_bucket=RelevanceBucket.IRRELEVANT_NOISE,
            relevance_score=0.15,
            exclusion_reason="Crash report unrelated to photo search",
        )
        self.assertFalse(noise_rec.is_relevant)

    def test_remembered_cue(self):
        """Verify memory cue model with support for polarity (negation)."""
        cue_positive = RememberedCue(
            cue_type=MemoryCueType.VISUAL_COLOR,
            detail="yellow jacket",
            is_negated=False,
        )
        self.assertFalse(cue_positive.is_negated)
        self.assertEqual(cue_positive.cue_type, MemoryCueType.VISUAL_COLOR)

        cue_negated = RememberedCue(
            cue_type=MemoryCueType.OBJECT_SCENE,
            detail="was not wearing a hat",
            is_negated=True,
        )
        self.assertTrue(cue_negated.is_negated)

    def test_memory_signal_record_verbatim_quote_validation(self):
        """Verify that verbatim quotes must exist in source text to prevent hallucinations."""
        source = "I tried searching for yellow jacket beach 2021 but only got pictures of bees."

        # Valid matching quote
        valid_record = MemorySignalRecord(
            record_id="rec_001",
            source_text=source,
            photo_type="candid vacation photo",
            remembered_cues=[
                RememberedCue(cue_type=MemoryCueType.VISUAL_COLOR, detail="yellow jacket"),
                RememberedCue(cue_type=MemoryCueType.SPATIAL, detail="beach"),
            ],
            forgotten_details=["exact date"],
            attempted_queries=["yellow jacket beach 2021"],
            failure_mode=SearchFailureMode.SEMANTIC_DRIFT,
            user_frustration_score=4,
            verbatim_quote="yellow jacket beach 2021 but only got pictures of bees",
        )
        self.assertEqual(valid_record.user_frustration_score, 4)

        # Invalid hallucinated quote should raise ValidationError
        with self.assertRaises(ValidationError) as ctx:
            MemorySignalRecord(
                record_id="rec_002",
                source_text=source,
                photo_type="candid vacation photo",
                failure_mode=SearchFailureMode.ZERO_RESULTS,
                user_frustration_score=3,
                verbatim_quote="This quote was hallucinated and never existed in source text",
            )
        self.assertIn("Verbatim quote", str(ctx.exception))

    def test_memory_signal_score_bounds(self):
        """Verify user_frustration_score bounds enforcement (1 to 5)."""
        source = "Valid text for testing score bounds"
        with self.assertRaises(ValidationError):
            MemorySignalRecord(
                record_id="rec_003",
                source_text=source,
                photo_type="screenshot",
                failure_mode=SearchFailureMode.ZERO_RESULTS,
                user_frustration_score=0,  # Below minimum 1
                verbatim_quote="Valid text",
            )

        with self.assertRaises(ValidationError):
            MemorySignalRecord(
                record_id="rec_004",
                source_text=source,
                photo_type="screenshot",
                failure_mode=SearchFailureMode.ZERO_RESULTS,
                user_frustration_score=6,  # Above maximum 5
                verbatim_quote="Valid text",
            )

    def test_problem_cluster_model(self):
        """Verify problem cluster metrics and schema representation."""
        cluster = ProblemCluster(
            cluster_id="cluster_01",
            cluster_title="Vague Visual & Temporal Recall Failure",
            description="Users remember high-level color or approximate season, but search yields zero results.",
            primary_failure_mode=SearchFailureMode.SEMANTIC_DRIFT,
            photo_types=["vacation", "portrait"],
            record_count=85,
            frequency_score=0.28,
            severity_score=4.2,
            retrieval_impact_index=round(0.28 * 4.2, 3),
            sample_record_ids=["rec_001", "rec_002"],
            representative_cues=["yellow shirt", "summer 2020"],
            top_verbatim_quotes=["I searched for yellow shirt and got bees"],
        )
        self.assertEqual(cluster.cluster_id, "cluster_01")
        self.assertAlmostEqual(cluster.retrieval_impact_index, 1.176, places=3)
        self.assertEqual(len(cluster.top_verbatim_quotes), 1)

    def test_opportunity_ranking_calculation(self):
        """Verify composite score calculation and weighting."""
        calculated_score = OpportunityRanking.calculate_composite_score(
            impact=4.5,
            evidence=4.0,
            feasibility=3.5,
            ux=4.0,
        )
        # Expected: 0.40*4.5 + 0.25*4.0 + 0.20*3.5 + 0.15*4.0 = 1.8 + 1.0 + 0.7 + 0.6 = 4.10
        self.assertEqual(calculated_score, 4.10)

        opp = OpportunityRanking(
            opportunity_id="opp_01",
            opportunity_title="Multi-Modal Visual Cue Refinement",
            target_cluster_ids=["cluster_01"],
            description="Enable conversational refinement for visual cues like color and setting.",
            impact_score=4.5,
            evidence_confidence=4.0,
            ml_feasibility=3.5,
            ux_addressability=4.0,
            composite_score=calculated_score,
            is_primary_recommendation=True,
        )
        self.assertTrue(opp.is_primary_recommendation)
        self.assertEqual(opp.composite_score, 4.10)

    def test_pipeline_checkpoint(self):
        """Verify checkpoint state tracking serialization."""
        ckpt = PipelineCheckpoint(
            pipeline_run_id="run_2026_10_06_001",
            started_at="2026-10-06T16:00:00Z",
            last_completed_stage="Stage 3: Cognitive Signal Extraction",
            records_ingested=500,
            records_sanitized=500,
            records_filtered=120,
            records_extracted=120,
            clusters_identified=6,
            is_complete=False,
        )
        json_data = ckpt.model_dump_json()
        deserialized = PipelineCheckpoint.model_validate_json(json_data)
        self.assertEqual(deserialized.records_extracted, 120)
        self.assertEqual(deserialized.last_completed_stage, "Stage 3: Cognitive Signal Extraction")


if __name__ == "__main__":
    unittest.main()
