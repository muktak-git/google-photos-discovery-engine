"""Unit tests for cognitive signal extractor and extraction pipeline in src/extraction."""

import json
import unittest
from pathlib import Path

from src.common.config import get_config
from src.common.schemas import MemoryCueType, MemorySignalRecord, SearchFailureMode
from src.extraction.extractor import CognitiveSignalExtractor
from src.extraction.pipeline import ExtractionPipeline
from src.extraction.prompt_templates import build_extraction_prompt


class TestExtraction(unittest.TestCase):
    """Test suite covering prompt generation, signal extraction, and pipeline persistence."""

    def setUp(self):
        self.config = get_config()
        self.config.ensure_directories()
        self.extractor = CognitiveSignalExtractor()

    def test_prompt_generation(self):
        text = "Looking for a photo of my dog on the beach"
        prompt = build_extraction_prompt(text)
        self.assertIn("Looking for a photo", prompt)
        self.assertIn("cognitive retrieval signals", prompt)

    def test_heuristic_extraction_fallback(self):
        """Verify fallback extraction generates valid MemorySignalRecord."""
        sample_text = (
            "I spent an hour looking for my car insurance receipt from Best Buy. "
            "I typed 'receipt car' and got zero results."
        )
        record = self.extractor._heuristic_extraction(
            record_id="rec_test_100",
            source_text=sample_text,
        )
        self.assertIsInstance(record, MemorySignalRecord)
        self.assertEqual(record.photo_type, "receipt")
        self.assertEqual(record.failure_mode, SearchFailureMode.OCR_FAILURE)
        self.assertIn(record.verbatim_quote.lower(), sample_text.lower())
        self.assertGreaterEqual(len(record.remembered_cues), 1)

    def test_extract_record_verbatim_guarantee(self):
        """Verify extract_record returns record where verbatim quote exists inside source_text."""
        sample_text = (
            "Looking for a photo of my friend wearing a bright yellow jacket on a hiking trail in Oregon back in 2021. "
            "When I search 'yellow jacket hiking', nothing comes up except photos of wasps! The algorithm is broken."
        )
        record = self.extractor.extract_record(
            record_id="rec_test_101",
            source_text=sample_text,
        )
        self.assertIsInstance(record, MemorySignalRecord)
        self.assertTrue(len(record.verbatim_quote) > 0)
        self.assertIn(record.verbatim_quote.lower(), sample_text.lower())
        self.assertGreaterEqual(record.user_frustration_score, 1)
        self.assertLessEqual(record.user_frustration_score, 5)

    def test_extraction_pipeline_execution(self):
        """Verify full extraction pipeline runs on retrieval conversations and outputs signals.jsonl."""
        pipeline = ExtractionPipeline()
        summary = pipeline.run_extraction()

        self.assertGreater(summary["total_extracted"], 0)
        self.assertEqual(summary["quote_verification_pass_rate"], 100.0)
        self.assertTrue(Path(summary["signals_output_path"]).exists())

        # Inspect persisted signals and assert quote inclusion
        with open(summary["signals_output_path"], "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertGreater(len(lines), 0)
            for line in lines:
                data = json.loads(line)
                rec = MemorySignalRecord.model_validate(data)
                # Hard gate: 100% of quotes MUST exist in source_text
                self.assertIn(
                    rec.verbatim_quote.strip().lower(),
                    rec.source_text.strip().lower(),
                )


if __name__ == "__main__":
    unittest.main()
