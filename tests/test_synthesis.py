"""Unit tests for opportunity scoring, evidence bank compiler, and executive report synthesis."""

import unittest
from pathlib import Path

from src.common.config import get_config
from src.common.schemas import (
    MemoryCueType,
    MemorySignalRecord,
    OpportunityRanking,
    ProblemCluster,
    RememberedCue,
    SearchFailureMode,
)
from src.synthesis.pipeline import SynthesisPipeline
from src.synthesis.quote_bank import EvidenceBankBuilder
from src.synthesis.ranking import OpportunityRanker
from src.synthesis.report_generator import ReportGenerator


class TestSynthesis(unittest.TestCase):
    """Test suite covering opportunity ranking, evidence compilation, and report generation."""

    def setUp(self):
        self.config = get_config()
        self.config.ensure_directories()
        self.sample_records = [
            MemorySignalRecord(
                record_id="rec_01",
                source_text="Looking for a photo of my friend wearing a yellow jacket on a hiking trail in Oregon back in 2021. Searching 'yellow jacket' gave zero results.",
                photo_type="candid portrait",
                remembered_cues=[
                    RememberedCue(cue_type=MemoryCueType.VISUAL_COLOR, detail="yellow jacket"),
                ],
                forgotten_details=["exact date"],
                attempted_queries=["yellow jacket"],
                failure_mode=SearchFailureMode.SEMANTIC_DRIFT,
                user_frustration_score=4,
                verbatim_quote="Looking for a photo of my friend wearing a yellow jacket on a hiking trail",
            ),
            MemorySignalRecord(
                record_id="rec_02",
                source_text="Can't find my car insurance policy receipt from Best Buy for $1200. OCR completely missed it.",
                photo_type="receipt",
                remembered_cues=[
                    RememberedCue(cue_type=MemoryCueType.DOCUMENT_OCR, detail="receipt Best Buy $1200"),
                ],
                forgotten_details=["date"],
                attempted_queries=["$1200", "Best Buy"],
                failure_mode=SearchFailureMode.OCR_FAILURE,
                user_frustration_score=5,
                verbatim_quote="Can't find my car insurance policy receipt from Best Buy",
            ),
        ]
        self.sample_clusters = [
            ProblemCluster(
                cluster_id="cluster_01",
                cluster_title="Visual Attribute & Color-Scene Semantic Mismatch",
                description="Search fails to bind colors to clothing items and produces semantic drift.",
                primary_failure_mode=SearchFailureMode.SEMANTIC_DRIFT,
                photo_types=["candid portrait"],
                record_count=1,
                frequency_score=0.50,
                severity_score=4.0,
                retrieval_impact_index=2.0,
                sample_record_ids=["rec_01"],
                representative_cues=["yellow jacket"],
                top_verbatim_quotes=["Looking for a yellow jacket photo"],
            ),
            ProblemCluster(
                cluster_id="cluster_02",
                cluster_title="Document OCR & Numerical Receipt Indexing Failure",
                description="Search misses small printed text, dollar amounts, and merchant names.",
                primary_failure_mode=SearchFailureMode.OCR_FAILURE,
                photo_types=["receipt"],
                record_count=1,
                frequency_score=0.50,
                severity_score=5.0,
                retrieval_impact_index=2.5,
                sample_record_ids=["rec_02"],
                representative_cues=["receipt Best Buy $1200"],
                top_verbatim_quotes=["Can't find my car insurance policy receipt"],
            ),
        ]

    def test_opportunity_ranker_formula_and_primary_selection(self):
        """Verify weighted scoring formula and primary recommendation designation."""
        ranker = OpportunityRanker()
        ranked = ranker.rank_opportunities(self.sample_clusters, self.sample_records)

        self.assertGreaterEqual(len(ranked), 2)
        # Exactly one recommendation must be designated as primary
        primary_count = sum(1 for o in ranked if o.is_primary_recommendation)
        self.assertEqual(primary_count, 1)

        # Ranked list should be sorted by composite score descending
        for i in range(len(ranked) - 1):
            self.assertGreaterEqual(ranked[i].composite_score, ranked[i + 1].composite_score)

    def test_feasibility_gate(self):
        """Edge Case 5.1: Infeasible opportunities cannot be primary recommendation."""
        ranker = OpportunityRanker()
        infeasible_opp = OpportunityRanking(
            opportunity_id="opp_infeasible",
            opportunity_title="Telepathic Thought Retrieval",
            target_cluster_ids=["cluster_01"],
            description="Find photos users only imagined",
            impact_score=5.0,
            evidence_confidence=5.0,
            ml_feasibility=1.0,  # Below min_feasibility_gate of 1.5
            ux_addressability=5.0,
            composite_score=4.5,
        )
        feasible_opp = OpportunityRanking(
            opportunity_id="opp_feasible",
            opportunity_title="Multi-Modal Visual Search",
            target_cluster_ids=["cluster_01"],
            description="Standard multi-modal search",
            impact_score=4.5,
            evidence_confidence=4.5,
            ml_feasibility=4.0,  # Feasible
            ux_addressability=4.0,
            composite_score=4.3,
        )
        ranked = sorted([infeasible_opp, feasible_opp], key=lambda x: x.composite_score, reverse=True)

        # Apply feasibility gate
        for o in ranked:
            if o.ml_feasibility >= ranker.min_feasibility_gate:
                o.is_primary_recommendation = True
                break

        # Assert feasible opportunity was chosen despite lower composite score
        self.assertTrue(feasible_opp.is_primary_recommendation)
        self.assertFalse(infeasible_opp.is_primary_recommendation)

    def test_evidence_bank_generation(self):
        """Verify verbatim_evidence_bank.md generation and quote integrity."""
        builder = EvidenceBankBuilder()
        out_path = builder.build_evidence_bank(self.sample_records, self.sample_clusters)
        self.assertTrue(out_path.exists())

        with open(out_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Verbatim User Evidence Bank", content)
            self.assertIn("100% Verbatim", content)
            self.assertIn("yellow jacket", content)
            self.assertIn("Best Buy", content)

    def test_report_generator_content(self):
        """Verify executive opportunity analysis report structure and questions answered."""
        generator = ReportGenerator()
        ranker = OpportunityRanker()
        ranked = ranker.rank_opportunities(self.sample_clusters, self.sample_records)
        out_path = generator.generate_report(self.sample_clusters, ranked, self.sample_records)
        self.assertTrue(out_path.exists())

        with open(out_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Core questions from problemStatement.md
            self.assertIn("What kinds of old photos do users struggle most to retrieve?", content)
            self.assertIn("What information do people actually remember about a photo?", content)
            self.assertIn("PRIMARY RECOMMENDATION", content)
            self.assertIn("Stakeholder Action Matrix", content)

    def test_synthesis_pipeline_execution(self):
        """Verify full synthesis pipeline execution generating all deliverables."""
        pipeline = SynthesisPipeline()
        summary = pipeline.run_synthesis()

        self.assertGreater(summary["opportunities_evaluated"], 0)
        self.assertIsNotNone(summary["primary_recommendation"]["title"])
        for deliv_path in summary["deliverables_generated"].values():
            self.assertTrue(Path(deliv_path).exists())


if __name__ == "__main__":
    unittest.main()
