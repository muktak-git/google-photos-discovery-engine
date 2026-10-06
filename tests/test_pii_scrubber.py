"""Unit tests for PII scrubbing and privacy sanitization in src/ingestion/pii_scrubber.py."""

import unittest
from src.common.schemas import RawConversationRecord
from src.ingestion.pii_scrubber import PIIScrubber


class TestPIIScrubber(unittest.TestCase):
    """Test suite ensuring 0% PII leakage and accurate entity detection."""

    def setUp(self):
        self.scrubber = PIIScrubber()

    def test_email_redaction(self):
        text = "Please reach out to support@myphotos.org or admin.user+tag@sub.domain.co.uk for help."
        cleaned, entities = self.scrubber.scrub_text(text)
        self.assertNotIn("support@myphotos.org", cleaned)
        self.assertNotIn("admin.user+tag@sub.domain.co.uk", cleaned)
        self.assertIn("[EMAIL]", cleaned)
        self.assertIn("EMAIL", entities)

    def test_phone_number_redaction(self):
        samples = [
            "Call me at (555) 234-5678 regarding the photo.",
            "Contact +1-800-555-0199 right away.",
            "Dial 555.123.4567 if needed.",
        ]
        for sample in samples:
            cleaned, entities = self.scrubber.scrub_text(sample)
            self.assertIn("[PHONE]", cleaned)
            self.assertIn("PHONE", entities)
            self.assertNotIn("555", cleaned)

    def test_ip_address_redaction(self):
        text_ipv4 = "Connected from client 192.168.1.100 while searching photos."
        cleaned, entities = self.scrubber.scrub_text(text_ipv4)
        self.assertNotIn("192.168.1.100", cleaned)
        self.assertIn("[IP]", cleaned)
        self.assertIn("IP", entities)

        text_ipv6 = "Server 2001:0db8:85a3:0000:0000:8a2e:0370:7334 dropped connection."
        cleaned_v6, entities_v6 = self.scrubber.scrub_text(text_ipv6)
        self.assertNotIn("2001:0db8", cleaned_v6)
        self.assertIn("[IP]", cleaned_v6)
        self.assertIn("IP", entities_v6)

    def test_user_handles_redaction(self):
        text = "Thanks to @photo_guru and u/shutterbug for the advice on Reddit."
        cleaned, entities = self.scrubber.scrub_text(text)
        self.assertNotIn("@photo_guru", cleaned)
        self.assertNotIn("u/shutterbug", cleaned)
        self.assertIn("[USER]", cleaned)
        self.assertIn("USER_HANDLE", entities)

    def test_device_identifier_redaction(self):
        uuid_text = "Crash log device UUID: 12345678-abcd-1234-ef01-123456789abc"
        cleaned_uuid, _ = self.scrubber.scrub_text(uuid_text)
        self.assertNotIn("12345678-abcd", cleaned_uuid)
        self.assertIn("[DEVICE]", cleaned_uuid)

        mac_text = "Device MAC 00:1A:2B:3C:4D:5E failed handshake."
        cleaned_mac, _ = self.scrubber.scrub_text(mac_text)
        self.assertNotIn("00:1A:2B:3C:4D:5E", cleaned_mac)
        self.assertIn("[DEVICE]", cleaned_mac)

        imei_text = "Phone IMEI is 490154203237518."
        cleaned_imei, _ = self.scrubber.scrub_text(imei_text)
        self.assertNotIn("490154203237518", cleaned_imei)
        self.assertIn("[DEVICE]", cleaned_imei)

    def test_kinship_name_redaction(self):
        """Edge Case 1.1: Kinship name references like 'Uncle Bob' or 'Aunt Sarah'."""
        text = "I'm looking for a photo of Uncle Bob and Aunt Sarah at the lake."
        cleaned, entities = self.scrubber.scrub_text(text)
        self.assertNotIn("Uncle Bob", cleaned)
        self.assertNotIn("Aunt Sarah", cleaned)
        self.assertIn("[FAMILY_MEMBER]", cleaned)
        self.assertIn("FAMILY_NAME", entities)

    def test_honorific_names_redaction(self):
        text = "Doctor Dr. Watson and Mr. Henderson took this photo."
        cleaned, entities = self.scrubber.scrub_text(text)
        self.assertNotIn("Dr. Watson", cleaned)
        self.assertNotIn("Mr. Henderson", cleaned)
        self.assertIn("[PERSON]", cleaned)
        self.assertIn("PERSON_NAME", entities)

    def test_possessive_name_redaction(self):
        text = "Searching for John's graduation picture from 2018."
        cleaned, entities = self.scrubber.scrub_text(text)
        self.assertNotIn("John's", cleaned)
        self.assertIn("[PERSON]'s", cleaned)
        self.assertIn("PERSON_NAME", entities)

    def test_gps_location_redaction(self):
        text = "Photo was taken near coordinates 37.7749, -122.4194 in California."
        cleaned, entities = self.scrubber.scrub_text(text)
        self.assertNotIn("37.7749", cleaned)
        self.assertIn("[LOCATION]", cleaned)
        self.assertIn("GPS_LOCATION", entities)

    def test_url_redaction(self):
        text = "Check out my profile at https://photos.google.com/share/AF1QipN?user=john_doe for samples."
        cleaned, entities = self.scrubber.scrub_text(text)
        self.assertNotIn("https://photos.google.com", cleaned)
        self.assertIn("[URL]", cleaned)
        self.assertIn("URL", entities)

    def test_scrub_record_full_lifecycle(self):
        """Verify transformation from RawConversationRecord to SanitizedConversationRecord."""
        raw = RawConversationRecord(
            raw_id="raw_test_99",
            source="community_forum",
            timestamp="2026-03-15T12:00:00Z",
            raw_text="Hello, I am contactable at alice@example.com or call 555-432-1098. Can't find Grandma Helen's recipe photo.",
            source_url="https://support.google.com/thread/123",
            metadata={"author": "alice_user", "client_ip": "10.0.0.1"},
        )
        sanitized = self.scrubber.scrub_record(raw)

        self.assertEqual(sanitized.raw_id, "raw_test_99")
        self.assertNotIn("alice@example.com", sanitized.sanitized_text)
        self.assertNotIn("555-432-1098", sanitized.sanitized_text)
        self.assertNotIn("Grandma Helen", sanitized.sanitized_text)
        self.assertEqual(sanitized.metadata["author"], "[REDACTED]")
        self.assertIn("EMAIL", sanitized.pii_detected)
        self.assertIn("PHONE", sanitized.pii_detected)
        self.assertIn("FAMILY_NAME", sanitized.pii_detected)


if __name__ == "__main__":
    unittest.main()
