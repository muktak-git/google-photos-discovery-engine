"""Google Play Store customer reviews ingestion adapter."""

from __future__ import annotations

import datetime
from typing import List

from src.common.logger import get_logger
from src.common.schemas import RawConversationRecord
from src.ingestion.base_adapter import BaseIngestionAdapter
from src.ingestion.fixtures import SAMPLE_PUBLIC_REVIEWS

logger = get_logger("Ingestion.PlayStore")


class PlayStoreAdapter(BaseIngestionAdapter):
    """Adapter for ingesting public user reviews from the Google Play Store."""

    def __init__(self, app_id: str = "com.google.android.apps.photos") -> None:
        super().__init__(source_name="play_store")
        self.app_id = app_id

    def fetch_records(self, limit: int = 1000) -> List[RawConversationRecord]:
        """Fetch raw reviews from Google Play Store live public API, falling back to fixtures if offline."""
        records: List[RawConversationRecord] = []

        # Attempt live ingestion using google_play_scraper
        try:
            from google_play_scraper import Sort, reviews

            fetch_count = min(max(limit, 100), 2000)
            fetched_reviews, _ = reviews(
                self.app_id,
                lang="en",
                country="us",
                sort=Sort.NEWEST,
                count=fetch_count,
            )

            for rev in fetched_reviews:
                content = rev.get("content", "").strip()
                review_id = rev.get("reviewId")
                at = rev.get("at")
                timestamp_str = (
                    at.isoformat()
                    if isinstance(at, (datetime.datetime, datetime.date))
                    else str(at or datetime.datetime.now(datetime.timezone.utc).isoformat())
                )

                if content and review_id:
                    records.append(
                        RawConversationRecord(
                            raw_id=f"ps_{review_id}",
                            source=self.source_name,
                            timestamp=timestamp_str,
                            raw_text=content,
                            source_url=f"https://play.google.com/store/apps/details?id={self.app_id}",
                            metadata={
                                "rating": rev.get("score"),
                                "thumbs_up": rev.get("thumbsUpCount", 0),
                                "review_created_version": rev.get("reviewCreatedVersion"),
                            },
                        )
                    )
            logger.info("Successfully fetched %d live Play Store reviews", len(records))

        except Exception as e:
            logger.warning(
                "Live Play Store scraping encountered exception: %s. Falling back to curated fixtures.",
                str(e),
            )

        # Always include or fall back to high-fidelity curated fixtures to ensure rich retrieval scenarios are present
        matching_fixtures = [
            r for r in SAMPLE_PUBLIC_REVIEWS if r.get("source") == "play_store"
        ]
        fixture_ids = {r.raw_id for r in records}
        for item in matching_fixtures:
            if item["raw_id"] not in fixture_ids:
                records.append(
                    RawConversationRecord(
                        raw_id=item["raw_id"],
                        source=self.source_name,
                        timestamp=item["timestamp"],
                        raw_text=item["raw_text"],
                        source_url=item.get("source_url"),
                        metadata=item.get("metadata", {}),
                    )
                )

        logger.info("Total Play Store records compiled: %d", len(records))
        return records[:limit]
