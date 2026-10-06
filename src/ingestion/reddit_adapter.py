"""Reddit public discussion threads ingestion adapter."""

from __future__ import annotations

import json
from typing import List

from src.common.logger import get_logger
from src.common.schemas import RawConversationRecord
from src.ingestion.base_adapter import BaseIngestionAdapter
from src.ingestion.fixtures import SAMPLE_PUBLIC_REVIEWS

logger = get_logger("Ingestion.Reddit")


class RedditAdapter(BaseIngestionAdapter):
    """Adapter for ingesting public discussions from Reddit subreddits."""

    def __init__(self, subreddit: str = "googlephotos") -> None:
        super().__init__(source_name="reddit")
        self.subreddit = subreddit
        self.url = f"https://www.reddit.com/r/{self.subreddit}/new.json?limit=25"

    def fetch_records(self, limit: int = 100) -> List[RawConversationRecord]:
        """Fetch raw posts from public Reddit feed or curated fixtures."""
        records: List[RawConversationRecord] = []

        feed_content = self._http_get(
            self.url,
            headers={"User-Agent": "Mozilla/5.0 ResearchBot/1.0"},
            max_retries=1,
        )

        if feed_content:
            try:
                data = json.loads(feed_content)
                children = data.get("data", {}).get("children", [])
                for child in children[:limit]:
                    post = child.get("data", {})
                    title = post.get("title", "")
                    selftext = post.get("selftext", "")
                    post_id = post.get("id", "")
                    created_utc = post.get("created_utc", 0)
                    permalink = post.get("permalink", "")

                    full_text = f"{title}. {selftext}".strip()
                    if post_id and full_text:
                        records.append(
                            RawConversationRecord(
                                raw_id=f"reddit_{post_id}",
                                source=self.source_name,
                                timestamp=str(created_utc),
                                raw_text=full_text,
                                source_url=f"https://reddit.com{permalink}",
                                metadata={
                                    "subreddit": self.subreddit,
                                    "upvotes": post.get("score", 0),
                                },
                            )
                        )
            except Exception as e:
                logger.warning("Error parsing Reddit feed: %s; using fixtures", str(e))

        if not records:
            matching_fixtures = [
                r for r in SAMPLE_PUBLIC_REVIEWS if r.get("source") == "reddit"
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

        logger.info("Ingested %d Reddit records", len(records))
        return records
