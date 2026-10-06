"""Apple App Store customer reviews ingestion adapter."""

from __future__ import annotations

import json
from typing import List

from src.common.logger import get_logger
from src.common.schemas import RawConversationRecord
from src.ingestion.base_adapter import BaseIngestionAdapter
from src.ingestion.fixtures import SAMPLE_PUBLIC_REVIEWS

logger = get_logger("Ingestion.AppStore")


class AppStoreAdapter(BaseIngestionAdapter):
    """Adapter for ingesting public user reviews from Apple App Store RSS feeds."""

    def __init__(self, app_id: str = "962194608", country: str = "us") -> None:
        super().__init__(source_name="app_store")
        self.app_id = app_id
        self.country = country

    def fetch_records(self, limit: int = 500) -> List[RawConversationRecord]:
        """Fetch raw reviews from Apple App Store RSS feed or curated fixture set."""
        records: List[RawConversationRecord] = []
        max_pages = min(10, max(1, (limit // 45) + 1))

        # Attempt to read from public RSS JSON feed across pages
        for page in range(1, max_pages + 1):
            if len(records) >= limit:
                break

            page_url = (
                f"https://itunes.apple.com/{self.country}/rss/customerreviews/"
                f"page={page}/id={self.app_id}/sortBy=mostRecent/json"
            )

            feed_content = self._http_get(page_url, max_retries=1)
            if not feed_content:
                break

            try:
                data = json.loads(feed_content)
                entries = data.get("feed", {}).get("entry", [])
                # First entry on page 1 is app metadata, subsequent entries are reviews
                review_entries = entries[1:] if page == 1 else entries

                for entry in review_entries:
                    if len(records) >= limit:
                        break

                    review_id = entry.get("id", {}).get("label", "")
                    content = entry.get("content", {}).get("label", "")
                    updated = entry.get("updated", {}).get("label", "")
                    rating = entry.get("im:rating", {}).get("label", "")

                    if review_id and content:
                        records.append(
                            RawConversationRecord(
                                raw_id=f"ios_{review_id}",
                                source=self.source_name,
                                timestamp=updated or "2026-01-01T00:00:00Z",
                                raw_text=content.strip(),
                                source_url=f"https://apps.apple.com/us/app/google-photos/id{self.app_id}",
                                metadata={"rating": int(rating) if rating.isdigit() else None},
                            )
                        )
            except Exception as e:
                logger.warning(
                    "Error parsing App Store live RSS feed page %d: %s", page, str(e)
                )
                break

        logger.info("Successfully fetched %d live App Store reviews", len(records))

        # Always include curated retrieval fixtures so specific cognitive retrieval scenarios are guaranteed
        matching_fixtures = [
            r for r in SAMPLE_PUBLIC_REVIEWS if r.get("source") == "app_store"
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

        logger.info("Total App Store records compiled: %d", len(records))
        return records[:limit]
