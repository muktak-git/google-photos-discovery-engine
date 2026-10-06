"""Data ingestion adapters and privacy sanitization modules."""

from src.ingestion.app_store import AppStoreAdapter
from src.ingestion.base_adapter import BaseIngestionAdapter
from src.ingestion.community_forum import CommunityForumAdapter
from src.ingestion.pii_scrubber import PIIScrubber
from src.ingestion.pipeline import IngestionPipeline
from src.ingestion.play_store import PlayStoreAdapter
from src.ingestion.reddit_adapter import RedditAdapter
from src.ingestion.youtube_adapter import YouTubeAdapter

__all__ = [
    "BaseIngestionAdapter",
    "PlayStoreAdapter",
    "AppStoreAdapter",
    "RedditAdapter",
    "CommunityForumAdapter",
    "YouTubeAdapter",
    "PIIScrubber",
    "IngestionPipeline",
]
