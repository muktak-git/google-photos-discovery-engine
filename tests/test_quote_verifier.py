"""Unit tests for deterministic quote verification and verbatim alignment in src/extraction/validator.py."""

import unittest
from src.extraction.validator import QuoteVerifier


class TestQuoteVerifier(unittest.TestCase):
    """Test suite ensuring 0% hallucination and exact source slicing."""

    def setUp(self):
        self.validator = QuoteVerifier()
        self.source = (
            "I spent two hours searching for a photo of my friend wearing a yellow jacket on a hiking trail in Oregon back in 2021. "
            "When I search 'yellow jacket hiking', nothing comes up except photos of wasps! The algorithm is completely broken."
        )

    def test_exact_substring_match(self):
        candidate = "wearing a yellow jacket on a hiking trail"
        is_valid, aligned, start, end = self.validator.verify_and_align_quote(
            self.source, candidate
        )
        self.assertTrue(is_valid)
        self.assertEqual(aligned, candidate)
        self.assertEqual(self.source[start:end], candidate)

    def test_case_insensitive_slice(self):
        candidate = "WEARING A YELLOW JACKET"
        is_valid, aligned, start, end = self.validator.verify_and_align_quote(
            self.source, candidate
        )
        self.assertTrue(is_valid)
        # Returns the casing as present in original source
        self.assertEqual(aligned, "wearing a yellow jacket")
        self.assertEqual(self.source[start:end], "wearing a yellow jacket")

    def test_whitespace_normalization(self):
        source_multi = "Searching for   receipt\n\nfrom Best Buy in 2022."
        candidate = "Searching for receipt from Best Buy"
        is_valid, aligned, start, end = self.validator.verify_and_align_quote(
            source_multi, candidate
        )
        self.assertTrue(is_valid)
        self.assertIn("Best Buy", aligned)
        self.assertEqual(source_multi[start:end], aligned)

    def test_fuzzy_alignment_typo_correction(self):
        """Edge Case 3.3: LLM fixes a typo, but verifier must slice authentic raw text."""
        source_with_typo = "I searched for my dogg in the snoww and it faild."
        # LLM normalized spelling
        llm_quote = "I searched for my dog in the snow and it failed."

        is_valid, aligned, start, end = self.validator.verify_and_align_quote(
            source_with_typo, llm_quote, min_similarity=0.88
        )
        self.assertTrue(is_valid)
        # Sliced text MUST match the raw source with original spelling
        self.assertEqual(aligned, "I searched for my dogg in the snoww and it faild.")
        self.assertEqual(source_with_typo[start:end], aligned)

    def test_hallucinated_quote_rejection(self):
        """Verifier must reject completely hallucinated quotes."""
        hallucinated = "This sentence was hallucinated by an LLM and does not exist."
        is_valid, aligned, start, end = self.validator.verify_and_align_quote(
            self.source, hallucinated
        )
        self.assertFalse(is_valid)
        self.assertEqual(aligned, "")
        self.assertIsNone(start)


if __name__ == "__main__":
    unittest.main()
