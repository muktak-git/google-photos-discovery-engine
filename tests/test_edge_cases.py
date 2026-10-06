"""Edge Case & Corner Scenario Automated Test Suite.

Validates the critical edge cases documented in edge-case.md:
1. Edge Case 1.1: Masking informal names & kinship references in queries.
2. Edge Case 2.1: Discarding sync/cloud data loss while accepting recall struggles.
3. Edge Case 3.1: Negated & disconfirmed memory cue separation.
4. Edge Case 3.3: Verbatim quote recovery via fuzzy alignment on LLM typo corrections.
5. Edge Case 4.1: HDBSCAN -1 noise outlier soft assignment (>= 0.72 threshold).
6. Edge Case 4.2: Hierarchical mega-cluster splitting (> 35% volume threshold).
7. Edge Case 5.1: Feasibility gate (M <= 1.5) disqualification of impossible requests.
"""

from __future__ import annotations

import unittest
import numpy as np

from src.clustering.clusterer import SemanticClusterer
from src.common.schemas import (
    MemoryCueType,
    MemorySignalRecord,
    OpportunityRanking,
    RememberedCue,
    SearchFailureMode,
)
from src.extraction.validator import QuoteVerifier
from src.filtering.heuristics import HeuristicFilter
from src.ingestion.pii_scrubber import PIIScrubber
from src.synthesis.ranking import OpportunityRanker


class TestEdgeCases(unittest.TestCase):
    """Automated tests for scenarios documented in edge-case.md."""

    def setUp(self) -> None:
        self.scrubber = PIIScrubber()
        self.heuristic_filter = HeuristicFilter()
        self.verifier = QuoteVerifier()
        self.ranker = OpportunityRanker()
        self.clusterer = SemanticClusterer()

    def test_pii_disguised_names_in_search(self) -> None:
        """Edge Case 1.1: Verify informal names and kinship references in queries are masked."""
        query_text = (
            "I tried searching for Uncle Bob's red canoe and Aunt Sarah's dog at john.doe@email.com "
            "with phone 415-555-1234"
        )
        sanitized, scrubbed_list = self.scrubber.scrub_text(query_text)

        # Ensure raw names and emails are gone
        self.assertNotIn("Bob", sanitized)
        self.assertNotIn("Sarah", sanitized)
        self.assertNotIn("john.doe@email.com", sanitized)
        self.assertNotIn("415-555-1234", sanitized)

        # Check mask markers
        self.assertIn("[FAMILY_MEMBER]", sanitized)
        self.assertIn("[EMAIL]", sanitized)
        self.assertIn("[PHONE]", sanitized)
        self.assertGreater(len(scrubbed_list), 0)

    def test_data_loss_vs_search_classification(self) -> None:
        """Edge Case 2.1: Verify data loss/sync failure is rejected while partial recall is accepted."""
        # 1. Permanent sync/cloud deletion complaint (out of scope)
        sync_loss_text = (
            "I can't find my vacation photos from 2021 anywhere, the app completely lost them "
            "after the update! Cloud sync wiped my entire library and deleted my pictures."
        )
        passed_sync, score_sync, reason_sync = self.heuristic_filter.evaluate(sync_loss_text)
        self.assertFalse(passed_sync, "Data loss complaint should be rejected by heuristic filter")
        self.assertIn("Cloud backup, deletion, or billing", reason_sync or "")

        # 2. Legitimate partial memory retrieval struggle (in scope)
        recall_text = (
            "I am trying to find a picture of my friend wearing a yellow jacket on a hiking trail in Oregon, "
            "I searched 'yellow jacket hiking' but it keeps failing to find it."
        )
        passed_recall, score_recall, reason_recall = self.heuristic_filter.evaluate(recall_text)
        self.assertTrue(passed_recall, "Legitimate partial memory search struggle should pass filter")
        self.assertGreater(score_recall, 0.5)

    def test_negated_cue_separation(self) -> None:
        """Edge Case 3.1: Verify negated memory cues are separated using is_negated attribute."""
        source_text = "I know for a fact it was not at the beach, and I was not wearing glasses, but search keeps showing beach pics."
        record = MemorySignalRecord(
            record_id="neg_01",
            source_text=source_text,
            photo_type="candid portrait",
            remembered_cues=[
                RememberedCue(cue_type=MemoryCueType.SPATIAL, detail="beach", is_negated=True),
                RememberedCue(cue_type=MemoryCueType.VISUAL_COLOR, detail="glasses", is_negated=True),
                RememberedCue(cue_type=MemoryCueType.VISUAL_COLOR, detail="black hoodie", is_negated=False),
            ],
            forgotten_details=["exact month", "exact year"],
            attempted_queries=["black hoodie outdoor"],
            failure_mode=SearchFailureMode.SEMANTIC_DRIFT,
            user_frustration_score=4,
            verbatim_quote="I know for a fact it was not at the beach",
        )

        # Check positive vs negated cues
        positive_cues = [c.detail for c in record.remembered_cues if not c.is_negated]
        negated_cues = [c.detail for c in record.remembered_cues if c.is_negated]

        self.assertEqual(positive_cues, ["black hoodie"])
        self.assertIn("beach", negated_cues)
        self.assertIn("glasses", negated_cues)

    def test_verbatim_quote_typo_resilience(self) -> None:
        """Edge Case 3.3: Verify fuzzy alignment recovers raw character slice when LLM fixes typos."""
        raw_source = "Yesterday I searched for my dogg in the snoww and it faild completely."
        # LLM normalized candidate with corrected typos
        llm_corrected_candidate = "I searched for my dog in the snow and it failed completely."

        # Verifier should align and return the raw, unedited character span from raw_source
        is_valid, verified_quote, start_idx, end_idx = self.verifier.verify_and_align_quote(
            raw_source, llm_corrected_candidate, min_similarity=0.85
        )

        self.assertTrue(is_valid)
        self.assertIsNotNone(verified_quote)
        # The returned quote MUST be an exact substring of raw_source
        self.assertIn(verified_quote, raw_source)
        self.assertIn("dogg", verified_quote)
        self.assertIn("snoww", verified_quote)
        self.assertEqual(raw_source[start_idx:end_idx], verified_quote)

    def test_hdbscan_noise_soft_reassignment(self) -> None:
        """Edge Case 4.1: Verify -1 outlier points are soft-assigned to nearest cluster if similarity >= 0.72."""
        # Synthetic embeddings: 4 vectors
        # 0 and 1 belong to cluster 0. Point 2 has high similarity (0.99) to cluster 0 centroid.
        # Point 3 is orthogonal (similarity 0.0)
        vectors = np.array([
            [1.0, 0.0, 0.0],
            [1.0, 0.02, 0.0],
            [0.98, 0.02, 0.0],  # Close enough to be soft-assigned (similarity >= 0.72)
            [0.0, 0.0, 1.0],   # Far outlier (similarity == 0.0)
        ])
        # L2 normalize
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / norms

        labels = np.array([0, 0, -1, -1])  # Points 2 and 3 initially marked noise

        updated_labels = self.clusterer._soft_assign_outliers(vectors, labels)

        # Point 2 should be reassigned to cluster 0
        self.assertEqual(updated_labels[2], 0)
        # Point 3 should remain unassigned (-1)
        self.assertEqual(updated_labels[3], -1)

    def test_mega_cluster_splitting(self) -> None:
        """Edge Case 4.2: Verify mega-clusters exceeding 35% of total volume are split."""
        # 10 records total. Cluster 'cluster_big' has 6 records (60% > 35%).
        # 'cluster_small' has 3 records (30% <= 35%) and should remain unsplit.
        cluster_map = {
            "cluster_big": [0, 1, 2, 3, 4, 5],
            "cluster_small": [6, 7, 8],
            "cluster_single": [9],
        }
        # Synthetic vectors
        vectors = np.random.RandomState(42).randn(10, 8)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / norms

        split_map = self.clusterer._split_mega_clusters(vectors, cluster_map, total_records=10)

        # 'cluster_big' should be replaced by at least two sub-clusters (e.g. cluster_big_sub0, cluster_big_sub1)
        self.assertNotIn("cluster_big", split_map)
        self.assertIn("cluster_small", split_map)
        self.assertGreaterEqual(len(split_map), 3)

    def test_feasibility_gate_on_unrealistic_requests(self) -> None:
        """Edge Case 5.1: Verify ML feasibility gate (M <= 1.5) disqualifies impossible user requests."""
        # Candidate A: Realistic opportunity with moderate composite score
        opp_realistic = OpportunityRanking(
            opportunity_id="opp_visual",
            opportunity_title="Multi-Modal Visual Cue & Color-Scene Contrast Retrieval",
            target_cluster_ids=["cluster_01"],
            description="Composition-aware multi-modal retrieval for visual attributes.",
            impact_score=4.5,
            evidence_confidence=4.0,
            ml_feasibility=4.2,  # Well above 1.5 gate
            ux_addressability=4.0,
            composite_score=4.24,
        )

        # Candidate B: Impossible request (Telepathic Emotion Reading), M = 1.0 (<= 1.5 gate), higher composite
        opp_impossible = OpportunityRanking(
            opportunity_id="opp_telepathy",
            opportunity_title="Telepathic Emotion & Vibe Direct Reading",
            target_cluster_ids=["cluster_02"],
            description="Read brainwaves to know what the user felt when taking the photo.",
            impact_score=5.0,
            evidence_confidence=5.0,
            ml_feasibility=1.0,  # Below feasibility gate of 1.5!
            ux_addressability=5.0,
            composite_score=4.35,  # Mathematically higher than opp_realistic
        )

        ranked = self.ranker.rank_opportunities(
            clusters=[],
            records=[],
            custom_candidates=[opp_impossible, opp_realistic],
        )

        # The primary recommendation MUST be the feasible opportunity
        primary = [o for o in ranked if o.is_primary_recommendation]
        self.assertEqual(len(primary), 1)
        self.assertEqual(primary[0].opportunity_id, "opp_visual")
        self.assertFalse(opp_impossible.is_primary_recommendation)


if __name__ == "__main__":
    unittest.main()
