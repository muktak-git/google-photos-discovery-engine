"""Google Photos Community Forum threads ingestion adapter."""

from __future__ import annotations

from typing import List

from src.common.logger import get_logger
from src.common.schemas import RawConversationRecord
from src.ingestion.base_adapter import BaseIngestionAdapter
from src.ingestion.fixtures import SAMPLE_PUBLIC_REVIEWS

logger = get_logger("Ingestion.CommunityForum")


class CommunityForumAdapter(BaseIngestionAdapter):
    """Adapter for ingesting public discussions from Google Photos support forums."""

    def __init__(self) -> None:
        super().__init__(source_name="community_forum")

    def fetch_records(self, limit: int = 100) -> List[RawConversationRecord]:
        """Fetch raw discussions from support community forum or curated fixtures."""
        records: List[RawConversationRecord] = []

        matching_fixtures = [
            r for r in SAMPLE_PUBLIC_REVIEWS if r.get("source") == "community_forum"
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

        logger.info("Ingested %d Community Forum records", len(records))
        return records
