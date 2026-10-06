"""Unit tests for ingestion adapters and pipeline runner in src/ingestion."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src.common.config import get_config
from src.common.schemas import RawConversationRecord, SanitizedConversationRecord
from src.ingestion.app_store import AppStoreAdapter
from src.ingestion.community_forum import CommunityForumAdapter
from src.ingestion.pipeline import IngestionPipeline
from src.ingestion.play_store import PlayStoreAdapter
from src.ingestion.reddit_adapter import RedditAdapter
from src.ingestion.youtube_adapter import YouTubeAdapter


class TestIngestion(unittest.TestCase):
    """Test suite covering data adapters and pipeline coordinator."""

    def setUp(self):
        self.config = get_config()
        self.config.ensure_directories()

    def test_play_store_adapter(self):
        adapter = PlayStoreAdapter()
        records = adapter.fetch_records(limit=5)
        self.assertGreaterEqual(len(records), 1)
        for r in records:
            self.assertIsInstance(r, RawConversationRecord)
            self.assertEqual(r.source, "play_store")
            self.assertTrue(len(r.raw_text) > 0)

    @patch.object(AppStoreAdapter, "_http_get", return_value=None)
    def test_app_store_adapter_offline(self, mock_http):
        adapter = AppStoreAdapter()
        records = adapter.fetch_records(limit=5)
        self.assertGreaterEqual(len(records), 1)
        for r in records:
            self.assertIsInstance(r, RawConversationRecord)
            self.assertEqual(r.source, "app_store")

    @patch.object(RedditAdapter, "_http_get", return_value=None)
    def test_reddit_adapter_offline(self, mock_http):
        adapter = RedditAdapter()
        records = adapter.fetch_records(limit=5)
        self.assertGreaterEqual(len(records), 1)
        for r in records:
            self.assertIsInstance(r, RawConversationRecord)
            self.assertEqual(r.source, "reddit")

    def test_community_forum_adapter(self):
        adapter = CommunityForumAdapter()
        records = adapter.fetch_records(limit=5)
        self.assertGreaterEqual(len(records), 1)
        for r in records:
            self.assertIsInstance(r, RawConversationRecord)
            self.assertEqual(r.source, "community_forum")

    def test_youtube_adapter(self):
        adapter = YouTubeAdapter()
        records = adapter.fetch_records(limit=5)
        self.assertGreaterEqual(len(records), 1)
        for r in records:
            self.assertIsInstance(r, RawConversationRecord)
            self.assertEqual(r.source, "youtube")

    @patch.object(AppStoreAdapter, "_http_get", return_value=None)
    @patch.object(RedditAdapter, "_http_get", return_value=None)
    def test_ingestion_pipeline_run(self, mock_reddit, mock_ios):
        """Verify full ingestion run across multiple sources and data lake persistence."""
        pipeline = IngestionPipeline()
        summary = pipeline.run_ingestion(
            sources=["play_store", "app_store", "reddit", "community_forum", "youtube"],
            limit_per_source=10,
        )

        self.assertGreaterEqual(summary["total_raw_records"], 5)
        self.assertGreaterEqual(summary["total_sanitized_records"], 5)
        self.assertTrue(Path(summary["master_raw_path"]).exists())
        self.assertTrue(Path(summary["master_sanitized_path"]).exists())

        # Validate master sanitized JSONL file contains valid SanitizedConversationRecords
        with open(summary["master_sanitized_path"], "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertGreater(len(lines), 0)
            for line in lines:
                data = json.loads(line)
                san_record = SanitizedConversationRecord.model_validate(data)
                self.assertTrue(len(san_record.record_id) > 0)
                # Verify that no raw email leaked in sanitized text
                self.assertNotIn("@example.com", san_record.sanitized_text)
                self.assertNotIn("@gmail.com", san_record.sanitized_text)


if __name__ == "__main__":
    unittest.main()
