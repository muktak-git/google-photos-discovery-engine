"""Privacy sanitization and PII scrubbing engine."""

from __future__ import annotations

import re
import uuid
from typing import List, Tuple

from src.common.config import get_config
from src.common.logger import get_logger
from src.common.schemas import RawConversationRecord, SanitizedConversationRecord

logger = get_logger("Ingestion.PIIScrubber")


class PIIScrubber:
    """Multi-pass deterministic PII redactor removing emails, phones, names, IPs, handles, and device IDs."""

    def __init__(self) -> None:
        self.config = get_config()
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regular expression patterns for maximum execution efficiency."""
        # Email address pattern
        self._email_re = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            re.IGNORECASE,
        )

        # Device identifiers: UUIDs, MAC addresses, IMEI-like 15 digit numbers
        self._uuid_re = re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
        )
        self._mac_re = re.compile(
            r"\b(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})\b"
        )
        self._imei_re = re.compile(r"\b\d{15}\b")

        # Phone numbers (US, international formats, with hyphens, parentheses, spaces)
        self._phone_re = re.compile(
            r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)"
        )

        # IPv4 and IPv6 addresses
        self._ipv4_re = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        self._ipv6_re = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b")

        # Social handles and user tags (@handle, u/username, /u/username)
        self._user_handle_re = re.compile(
            r"(?:@|/?u/)[A-Za-z0-9_-]{3,30}\b",
            re.IGNORECASE,
        )

        # URLs with tracking tokens or personal parameters
        self._url_re = re.compile(
            r"https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_+.~#?&/=]*",
            re.IGNORECASE,
        )

        # Kinship + Name references (Edge Case 1.1: "Uncle Bob", "Aunt Sarah", "Grandma Rose", etc.)
        self._kinship_re = re.compile(
            r"\b(?:uncle|aunt|cousin|grandpa|grandmother|grandma|grandfather|brother|sister|mom|dad)\s+([A-Z][a-z]{1,20})\b",
            re.IGNORECASE,
        )

        # Honorifics + Proper Names ("Mr. Smith", "Dr. Jane Watson", "Prof. Davis")
        self._honorific_name_re = re.compile(
            r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s+[A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20})?\b"
        )

        # Common first names in possessive or subject query patterns (e.g., "John's birthday", "Dave and Sarah")
        common_names = (
            "John|Jane|Bob|Alice|Michael|Sarah|David|Emily|James|Jessica|"
            "Robert|Ashley|William|Amanda|Brian|Megan|Matthew|Rachel|Daniel|"
            "Joshua|Andrew|Christopher|Joseph|Elizabeth|Mary|Patricia|Jennifer|"
            "Linda|Barbara|Richard|Thomas|Charles|Mark|Donald|Steven|Paul|Kevin"
        )
        self._common_name_possessive_re = re.compile(
            rf"\b({common_names})'s\b",
            re.IGNORECASE,
        )

        # GPS Coordinates (e.g. 37.7749° N, 122.4194° W or decimal 37.7749, -122.4194)
        self._gps_re = re.compile(
            r"\b[-+]?([1-8]?\d(?:\.\d+)?|90(?:\.0+)?),\s*[-+]?(180(?:\.0+)?|(?:1[0-7]\d|\d{1,2})(?:\.\d+)?)\b"
        )

    def scrub_text(self, text: str) -> Tuple[str, List[str]]:
        """Scrub PII entities from text and return (sanitized_text, detected_entity_types)."""
        if not text:
            return text, []

        pii_found: List[str] = []
        sanitized = text

        # 1. Email Redaction
        if self._email_re.search(sanitized):
            sanitized = self._email_re.sub("[EMAIL]", sanitized)
            pii_found.append("EMAIL")

        # 2. Device identifiers (UUID, MAC, IMEI) - checked before phone numbers
        if (
            self._uuid_re.search(sanitized)
            or self._mac_re.search(sanitized)
            or self._imei_re.search(sanitized)
        ):
            sanitized = self._uuid_re.sub("[DEVICE]", sanitized)
            sanitized = self._mac_re.sub("[DEVICE]", sanitized)
            sanitized = self._imei_re.sub("[DEVICE]", sanitized)
            pii_found.append("DEVICE_ID")

        # 3. Phone Redaction
        if self._phone_re.search(sanitized):
            sanitized = self._phone_re.sub("[PHONE]", sanitized)
            pii_found.append("PHONE")

        # 4. IP Redaction (v4 and v6)
        if self._ipv4_re.search(sanitized) or self._ipv6_re.search(sanitized):
            sanitized = self._ipv4_re.sub("[IP]", sanitized)
            sanitized = self._ipv6_re.sub("[IP]", sanitized)
            pii_found.append("IP")

        # 5. User handles (@user, u/user)
        if self._user_handle_re.search(sanitized):
            sanitized = self._user_handle_re.sub("[USER]", sanitized)
            pii_found.append("USER_HANDLE")

        # 6. GPS coordinates
        if self._gps_re.search(sanitized):
            sanitized = self._gps_re.sub("[LOCATION]", sanitized)
            pii_found.append("GPS_LOCATION")

        # 7. Kinship + Name references (Edge Case 1.1)
        if self._kinship_re.search(sanitized):
            sanitized = self._kinship_re.sub(r"[FAMILY_MEMBER]", sanitized)
            pii_found.append("FAMILY_NAME")

        # 8. Honorific + Names
        if self._honorific_name_re.search(sanitized):
            sanitized = self._honorific_name_re.sub("[PERSON]", sanitized)
            pii_found.append("PERSON_NAME")

        # 9. Possessive common names (e.g., "John's" -> "[PERSON]'s")
        if self._common_name_possessive_re.search(sanitized):
            sanitized = self._common_name_possessive_re.sub(r"[PERSON]'s", sanitized)
            pii_found.append("PERSON_NAME")

        # 10. URL Redaction
        if self._url_re.search(sanitized):
            sanitized = self._url_re.sub("[URL]", sanitized)
            pii_found.append("URL")

        return sanitized, sorted(list(set(pii_found)))

    def scrub_record(self, raw_record: RawConversationRecord) -> SanitizedConversationRecord:
        """Convert a raw conversation record into a privacy-scrubbed record with full lineage."""
        sanitized_text, pii_detected = self.scrub_text(raw_record.raw_text)

        # Generate a deterministic or unique record_id
        record_id = f"rec_{uuid.uuid5(uuid.NAMESPACE_DNS, raw_record.raw_id).hex[:12]}"

        # Clean metadata to ensure no usernames or emails leaked
        safe_metadata = {}
        for k, v in raw_record.metadata.items():
            if k.lower() in ("author", "username", "user", "email", "ip", "device_id"):
                safe_metadata[k] = "[REDACTED]"
            elif isinstance(v, str):
                cleaned_v, _ = self.scrub_text(v)
                safe_metadata[k] = cleaned_v
            else:
                safe_metadata[k] = v

        return SanitizedConversationRecord(
            record_id=record_id,
            raw_id=raw_record.raw_id,
            source=raw_record.source,
            timestamp=raw_record.timestamp,
            source_url=raw_record.source_url,
            sanitized_text=sanitized_text,
            pii_detected=pii_detected,
            metadata=safe_metadata,
        )
