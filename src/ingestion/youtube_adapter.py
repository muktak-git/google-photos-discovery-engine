"""YouTube public video comments ingestion adapter."""

from __future__ import annotations

from typing import List

from src.common.logger import get_logger
from src.common.schemas import RawConversationRecord
from src.ingestion.base_adapter import BaseIngestionAdapter
from src.ingestion.fixtures import SAMPLE_PUBLIC_REVIEWS

logger = get_logger("Ingestion.YouTube")


class YouTubeAdapter(BaseIngestionAdapter):
    """Adapter for ingesting public video comments from photo walkthrough videos."""

    def __init__(self) -> None:
        super().__init__(source_name="youtube")

    def fetch_records(self, limit: int = 100) -> List[RawConversationRecord]:
        """Fetch raw public comments from YouTube videos or curated fixtures."""
        records: List[RawConversationRecord] = []

        matching_fixtures = [
            r for r in SAMPLE_PUBLIC_REVIEWS if r.get("source") == "youtube"
        ]
        for item in matching_fixtures[:limit]:
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

        logger.info("Ingested %d YouTube records", len(records))
        return records
