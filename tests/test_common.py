"""Unit tests for config and logging in src/common."""

import os
import unittest
from pathlib import Path

from src.common.config import EngineConfig, get_config
from src.common.logger import PIIRedactionFilter, get_logger, setup_logger


class TestCommon(unittest.TestCase):
    """Test suite covering configuration loading and logger behavior."""

    def test_config_initialization(self):
        """Verify EngineConfig initializes defaults and creates directory structures."""
        config = get_config()
        self.assertEqual(config.app_name, "GooglePhotosEngine")
        self.assertTrue(config.data_dir.exists())
        self.assertTrue(config.raw_dir.exists())
        self.assertTrue(config.sanitized_dir.exists())
        self.assertTrue(config.filtered_dir.exists())
        self.assertTrue(config.extracted_dir.exists())
        self.assertTrue(config.output_dir.exists())
        self.assertTrue(config.logs_dir.exists())

        config_dict = config.to_dict()
        self.assertIn("paths", config_dict)
        self.assertEqual(config_dict["weights"]["impact"], 0.40)

    def test_logger_setup(self):
        """Verify logger instantiation and message emission."""
        logger = setup_logger("TestLogger", level="DEBUG", log_to_file=False)
        self.assertEqual(logger.name, "TestLogger")
        self.assertGreaterEqual(len(logger.handlers), 1)

    def test_pii_redaction_filter(self):
        """Verify that PIIRedactionFilter masks emails, phones, and IPs."""
        import logging

        filt = PIIRedactionFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="User john.doe@example.com called 555-123-4567 from 192.168.1.1",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        self.assertNotIn("john.doe@example.com", record.msg)
        self.assertIn("[EMAIL]", record.msg)
        self.assertNotIn("555-123-4567", record.msg)
        self.assertIn("[PHONE]", record.msg)
        self.assertNotIn("192.168.1.1", record.msg)
        self.assertIn("[IP]", record.msg)


if __name__ == "__main__":
    unittest.main()
