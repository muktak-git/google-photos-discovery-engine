"""Ingestion and privacy sanitization pipeline coordinator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.common.config import get_config
from src.common.logger import get_logger
from src.common.schemas import RawConversationRecord, SanitizedConversationRecord
from src.ingestion.app_store import AppStoreAdapter
from src.ingestion.community_forum import CommunityForumAdapter
from src.ingestion.pii_scrubber import PIIScrubber
from src.ingestion.play_store import PlayStoreAdapter
from src.ingestion.reddit_adapter import RedditAdapter
from src.ingestion.youtube_adapter import YouTubeAdapter

logger = get_logger("Ingestion.Pipeline")


class IngestionPipeline:
    """Orchestrates multi-source ingestion and privacy sanitization."""

    def __init__(self) -> None:
        self.config = get_config()
        self.scrubber = PIIScrubber()
        self.adapters = {
            "play_store": PlayStoreAdapter(),
            "app_store": AppStoreAdapter(),
            "reddit": RedditAdapter(),
            "community_forum": CommunityForumAdapter(),
            "youtube": YouTubeAdapter(),
        }

    @staticmethod
    def is_useful_review(text: str) -> bool:
        """Determines if a review is substantive and useful for analytical discovery.

        Excludes low-information noise:
        - Pure emojis or rating symbols (e.g. ⭐⭐⭐⭐⭐, 👍, ❤️)
        - Very short ratings (< 20 characters or < 5 words)
        - Generic one-liners without narrative (e.g. 'good app', 'nice', 'love it')
        """
        clean = text.strip()
        if len(clean) < 20:
            return False
        words = clean.split()
        if len(words) < 5:
            return False
        # Must contain alphabetical letters (not pure emojis, numbers, or symbols)
        if not any(c.isalpha() for c in clean):
            return False
        generic = {
            "good app", "great app", "nice app", "best app", "love it",
            "very good", "very nice", "awesome app", "cool app", "five stars",
            "good photo app", "best photo app", "thank you", "thanks google",
            "bad app", "worst app", "not good", "update ruined it",
            "hate this app", "perfect app", "super app"
        }
        lower = clean.lower().rstrip("!., ")
        if lower in generic:
            return False
        return True

    def run_ingestion(
        self,
        sources: Optional[List[str]] = None,
        limit_per_source: int = 1000,
    ) -> Dict[str, Any]:
        """Runs ingestion across designated sources, scrubs PII, filters for actual useful reviews, and persists datasets."""
        self.config.ensure_directories()
        target_sources = sources or list(self.adapters.keys())

        total_raw = 0
        total_useful_sanitized = 0
        total_low_info_excluded = 0
        pii_entity_counts: Dict[str, int] = {}
        all_sanitized_records: List[SanitizedConversationRecord] = []

        master_raw_path = self.config.raw_dir / "all_raw_conversations.jsonl"
        master_sanitized_path = self.config.sanitized_dir / "sanitized_conversations.jsonl"

        # Truncate or initialize master run files
        with open(master_raw_path, "w", encoding="utf-8") as raw_f, open(
            master_sanitized_path, "w", encoding="utf-8"
        ) as san_f:
            for source_name in target_sources:
                adapter = self.adapters.get(source_name)
                if not adapter:
                    logger.warning("Unknown source adapter requested: %s", source_name)
                    continue

                logger.info("Starting ingestion for source: %s", source_name)
                raw_records = adapter.fetch_records(limit=limit_per_source)
                total_raw += len(raw_records)

                # Persist raw records per source and in master
                source_raw_path = self.config.raw_dir / f"{source_name}_raw.jsonl"
                with open(source_raw_path, "w", encoding="utf-8") as s_raw_f:
                    for rec in raw_records:
                        line = rec.model_dump_json()
                        s_raw_f.write(line + "\n")
                        raw_f.write(line + "\n")

                # Scrub PII & filter for actual useful reviews
                source_sanitized_path = self.config.sanitized_dir / f"{source_name}_sanitized.jsonl"
                with open(source_sanitized_path, "w", encoding="utf-8") as s_san_f:
                    for raw_rec in raw_records:
                        san_rec = self.scrubber.scrub_record(raw_rec)
                        for entity_type in san_rec.pii_detected:
                            pii_entity_counts[entity_type] = (
                                pii_entity_counts.get(entity_type, 0) + 1
                            )

                        # Filter for actual useful reviews
                        if self.is_useful_review(san_rec.sanitized_text):
                            all_sanitized_records.append(san_rec)
                            total_useful_sanitized += 1
                            line = san_rec.model_dump_json()
                            s_san_f.write(line + "\n")
                            san_f.write(line + "\n")
                        else:
                            total_low_info_excluded += 1

        summary = {
            "sources_processed": target_sources,
            "total_raw_records": total_raw,
            "total_sanitized_records": total_useful_sanitized,
            "total_useful_cleaned": total_useful_sanitized,
            "low_info_spam_excluded": total_low_info_excluded,
            "pii_entity_counts": pii_entity_counts,
            "master_raw_path": str(master_raw_path),
            "master_sanitized_path": str(master_sanitized_path),
        }

        logger.info(
            "Phase 1 Ingestion Complete. Ingested: %d, Useful Cleaned: %d (Excluded %d spam/low-info), PII Entities Scrubbed: %s",
            total_raw,
            total_useful_sanitized,
            total_low_info_excluded,
            json.dumps(pii_entity_counts),
        )
        return summary
