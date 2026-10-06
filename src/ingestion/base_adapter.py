"""Abstract base adapter for collecting public feedback discussions."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.common.config import get_config
from src.common.logger import get_logger
from src.common.schemas import RawConversationRecord

logger = get_logger("Ingestion.BaseAdapter")


class BaseIngestionAdapter(ABC):
    """Abstract interface for all public conversation source connectors."""

    def __init__(self, source_name: str, rate_limit_delay: Optional[float] = None) -> None:
        self.source_name = source_name
        self.config = get_config()
        self.rate_limit_delay = (
            rate_limit_delay
            if rate_limit_delay is not None
            else self.config.rate_limit_delay_seconds
        )
        self.default_headers: Dict[str, str] = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PhotoDiscoveryEngine/0.1.0 (Public Research Bot)",
            "Accept": "application/json, application/xml, text/plain, */*",
        }

    @abstractmethod
    def fetch_records(self, limit: int = 100) -> List[RawConversationRecord]:
        """Fetch raw conversation records from the target source."""
        pass

    def _http_get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 15,
        max_retries: int = 3,
    ) -> Optional[str]:
        """Execute a rate-limited, resilient HTTP GET request using standard library."""
        req_headers = {**self.default_headers, **(headers or {})}
        request = urllib.request.Request(url, headers=req_headers)

        for attempt in range(1, max_retries + 1):
            try:
                # Obey rate limiting delay
                if self.rate_limit_delay > 0:
                    time.sleep(self.rate_limit_delay)

                with urllib.request.urlopen(request, timeout=timeout) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    return response.read().decode(charset, errors="replace")

            except urllib.error.HTTPError as e:
                logger.warning(
                    "HTTP %s fetching %s (attempt %d/%d): %s",
                    e.code,
                    url,
                    attempt,
                    max_retries,
                    e.reason,
                )
                if e.code == 429:
                    # Jittered backoff on rate limit
                    backoff = (2**attempt) * 1.5
                    time.sleep(backoff)
                elif 400 <= e.code < 500:
                    # Client errors (e.g. 404) are usually not retryable
                    return None
            except urllib.error.URLError as e:
                logger.warning(
                    "Connection error fetching %s (attempt %d/%d): %s",
                    url,
                    attempt,
                    max_retries,
                    e.reason,
                )
                time.sleep(2**attempt)
            except Exception as e:
                logger.error("Unexpected error fetching %s: %s", url, str(e))
                return None

        return None

    def save_raw_records(
        self,
        records: List[RawConversationRecord],
        output_path: Optional[Path] = None,
    ) -> Path:
        """Persist raw records in append-only JSONL format to the data lake."""
        self.config.ensure_directories()
        target_path = output_path or (self.config.raw_dir / f"{self.source_name}_records.jsonl")

        with open(target_path, "a", encoding="utf-8") as f:
            for record in records:
                f.write(record.model_dump_json() + "\n")

        logger.info(
            "Saved %d raw records for source '%s' to %s",
            len(records),
            self.source_name,
            target_path,
        )
        return target_path
