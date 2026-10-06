"""Unit tests and precision benchmark for Tier 1 and Tier 2 filtering."""

import json
import unittest
from pathlib import Path

from src.common.config import get_config
from src.common.schemas import (
    FilteredConversationRecord,
    RelevanceBucket,
    SanitizedConversationRecord,
)
from src.filtering.classifier import IntentClassifier
from src.filtering.heuristics import HeuristicFilter
from src.filtering.pipeline import FilteringPipeline


class TestFiltering(unittest.TestCase):
    """Test suite covering lexical heuristics, intent classification, and pipeline execution."""

    def setUp(self):
        self.config = get_config()
        self.config.ensure_directories()
        self.heuristics = HeuristicFilter()
        self.classifier = IntentClassifier()

    def test_tier1_valid_retrieval(self):
        text = "I'm searching for an old photo of my dog wearing a red bandana from 3 years ago."
        passes, score, reason = self.heuristics.evaluate(text)
        self.assertTrue(passes)
        self.assertGreater(score, 0.6)
        self.assertIsNone(reason)

    def test_tier1_micro_review_rejection(self):
        """Edge Case 1.3: Micro-reviews with insufficient cognitive context."""
        short_text = "can't find pic"
        passes, score, reason = self.heuristics.evaluate(short_text)
        self.assertFalse(passes)
        self.assertIn("Micro-review", reason)

    def test_tier1_pure_data_loss_rejection(self):
        """Edge Case 2.1: Cloud sync deletion vs memory retrieval."""
        loss_text = "Google Photos deleted all my photos after the update! My 2020 backup is gone!"
        passes, score, reason = self.heuristics.evaluate(loss_text)
        self.assertFalse(passes)
        self.assertIn("Cloud backup, deletion, or billing issue", reason)

    def test_tier1_pure_crash_rejection(self):
        crash_text = "The app keeps crashing and freezing whenever I open the library view."
        passes, score, reason = self.heuristics.evaluate(crash_text)
        self.assertFalse(passes)
        self.assertIn("Application stability", reason)

    def test_tier2_partial_memory_classification(self):
        text = "Looking for a photo of my friend wearing a yellow jacket on a hiking trail in Oregon back in 2021. Searching 'yellow jacket' gave zero results."
        bucket, score, reason = self.classifier.classify_text(text)
        self.assertEqual(bucket, RelevanceBucket.RELEVANT_PARTIAL_MEMORY)
        self.assertGreaterEqual(score, 0.70)
        self.assertIsNone(reason)

    def test_tier2_ocr_receipt_retrieval(self):
        text = "I need to find my car insurance policy photo from last year. I searched 'insurance car' and it gives me random cars on the street instead of the document."
        bucket, score, reason = self.classifier.classify_text(text)
        self.assertEqual(bucket, RelevanceBucket.RELEVANT_PARTIAL_MEMORY)
        self.assertGreaterEqual(score, 0.70)

    def test_tier2_mixed_intent_handling(self):
        """Edge Case 2.2: Positive praise mixed with deep search frustration."""
        mixed_text = "Best photo app ever, automatic backup is great, but honestly whenever I try to find a picture of my car insurance slip by typing 'insurance car' it gives me random cars."
        bucket, score, reason = self.classifier.classify_text(mixed_text)
        self.assertEqual(bucket, RelevanceBucket.RELEVANT_PARTIAL_MEMORY)

    def test_tier2_sarcasm_idiom_rejection(self):
        """Edge Case 2.3: Pure idiom without concrete memory cues."""
        sarcasm_text = "Searching in this app is like finding a needle in a haystack. What a complete joke."
        bucket, score, reason = self.classifier.classify_text(sarcasm_text)
        self.assertEqual(bucket, RelevanceBucket.IRRELEVANT_NOISE)

    def test_tier2_general_search_ui_usability(self):
        ui_text = "The search bar should be moved to the bottom of the screen because the keyboard covers search on my phone."
        bucket, score, reason = self.classifier.classify_text(ui_text)
        self.assertEqual(bucket, RelevanceBucket.GENERAL_SEARCH_USABILITY)

    def test_precision_benchmark(self):
        """Precision benchmark on labeled evaluation dataset (Target: >= 90% precision)."""
        labeled_dataset = [
            # Ground truth: Positive (RELEVANT_PARTIAL_MEMORY)
            ("Looking for a photo of my friend wearing a yellow jacket hiking in 2021", True),
            ("Can't find the photo of my wifi router password sticker from two years ago", True),
            ("Searching for receipt from Best Buy around $1200 from summer 2022 and got nothing", True),
            ("Trying to find a picture of [PERSON] standing in front of a red barn in Vermont back in 2018", True),
            ("Photos taken right before the pandemic started, searching summer 2019 gives nothing", True),
            ("I remember the recipe screenshot had pistachio and lemon curd, but typing recipe brings up nothing", True),
            ("Looking for the picture where [PERSON] was not smiling and wearing a black hoodie", True),
            # Ground truth: Negative (Noise or Usability)
            ("Great cloud backup! Best photo app on the iPhone.", False),
            ("Google Photos deleted my entire 2020 backup from cloud storage!", False),
            ("The app keeps crashing whenever I scroll past November 2023.", False),
            ("Search is like finding a needle in a haystack, total joke.", False),
            ("Please move the search bar position to the bottom of the screen.", False),
            ("Can't find pic", False),
            ("I need a refund for my Google One 100 GB storage subscription payment.", False),
        ]

        true_positives = 0
        false_positives = 0
        true_negatives = 0
        false_negatives = 0

        for text, is_true_positive in labeled_dataset:
            # Run two-tier evaluation
            passes_t1, _, _ = self.heuristics.evaluate(text)
            if passes_t1:
                bucket, _, _ = self.classifier.classify_text(text)
                predicted_positive = bucket == RelevanceBucket.RELEVANT_PARTIAL_MEMORY
            else:
                predicted_positive = False

            if is_true_positive and predicted_positive:
                true_positives += 1
            elif not is_true_positive and predicted_positive:
                false_positives += 1
            elif not is_true_positive and not predicted_positive:
                true_negatives += 1
            else:
                false_negatives += 1

        precision = (
            true_positives / (true_positives + false_positives)
            if (true_positives + false_positives) > 0
            else 0.0
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if (true_positives + false_negatives) > 0
            else 0.0
        )

        # Assert precision meets or exceeds project requirement (>= 90%)
        self.assertGreaterEqual(
            precision,
            0.90,
            f"Precision {precision:.2f} did not meet 90% benchmark! (TP={true_positives}, FP={false_positives})",
        )
        self.assertGreaterEqual(recall, 0.85, f"Recall {recall:.2f} below 85%")

    def test_filtering_pipeline_execution(self):
        """Verify full filtering pipeline execution on sanitized records lake."""
        pipeline = FilteringPipeline()
        summary = pipeline.run_filtering()

        self.assertGreater(summary["total_processed"], 0)
        self.assertGreater(summary["relevant_retrieval_records"], 0)
        self.assertTrue(Path(summary["retrieval_output_path"]).exists())
        self.assertTrue(Path(summary["master_output_path"]).exists())

        # Verify output records validate against FilteredConversationRecord
        with open(summary["retrieval_output_path"], "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertGreater(len(lines), 0)
            for line in lines:
                data = json.loads(line)
                rec = FilteredConversationRecord.model_validate(data)
                self.assertTrue(rec.is_relevant)
                self.assertEqual(rec.relevance_bucket, RelevanceBucket.RELEVANT_PARTIAL_MEMORY)


if __name__ == "__main__":
    unittest.main()
