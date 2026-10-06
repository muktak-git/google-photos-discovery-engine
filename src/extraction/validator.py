"""Deterministic verbatim quote verifier and alignment engine."""

from __future__ import annotations

import difflib
import re
from typing import Optional, Tuple

from src.common.logger import get_logger

logger = get_logger("Extraction.Validator")


class QuoteVerifier:
    """Verifies that extracted quotes exist verbatim in source text and recovers exact character slices."""

    @staticmethod
    def verify_and_align_quote(
        source_text: str, candidate_quote: str, min_similarity: float = 0.90
    ) -> Tuple[bool, str, Optional[int], Optional[int]]:
        """Verifies candidate quote against source text.

        Returns:
            (is_valid, verbatim_quote, start_idx, end_idx)
        """
        if not source_text or not candidate_quote:
            return False, "", None, None

        clean_candidate = candidate_quote.strip().strip("'\"“”")
        if len(clean_candidate) < 3:
            return False, "", None, None

        # 1. Exact substring match
        start_idx = source_text.find(clean_candidate)
        if start_idx != -1:
            end_idx = start_idx + len(clean_candidate)
            return True, clean_candidate, start_idx, end_idx

        # 2. Case-insensitive substring match
        source_lower = source_text.lower()
        candidate_lower = clean_candidate.lower()
        start_idx = source_lower.find(candidate_lower)
        if start_idx != -1:
            end_idx = start_idx + len(candidate_lower)
            # Return the exact slice from original source_text
            exact_slice = source_text[start_idx:end_idx]
            return True, exact_slice, start_idx, end_idx

        # 3. Normalized whitespace match
        source_words = source_text.split()
        candidate_words = clean_candidate.split()
        cand_len = len(candidate_words)

        if cand_len > 0:
            for i in range(len(source_words) - cand_len + 1):
                window = " ".join(source_words[i : i + cand_len])
                if window.lower() == " ".join(candidate_words).lower():
                    # Find span in original text
                    # Search regex constructed from words
                    pattern = r"\s+".join(re.escape(w) for w in candidate_words)
                    m = re.search(pattern, source_text, re.IGNORECASE)
                    if m:
                        return True, m.group(0), m.start(), m.end()

        # 4. Fuzzy sliding window alignment for minor LLM typo fixes (Edge Case 3.3)
        # LLM may have corrected a typo like "recieve" -> "receive" or changed punctuation
        cand_char_len = len(clean_candidate)
        best_ratio = 0.0
        best_slice = ""
        best_start = -1
        best_end = -1

        # Search windows within ±15% length of candidate quote
        step = max(1, cand_char_len // 10)
        for i in range(0, max(1, len(source_text) - cand_char_len + 1), step):
            for length_delta in range(-5, 6):
                w_len = cand_char_len + length_delta
                if w_len <= 0 or i + w_len > len(source_text):
                    continue
                window = source_text[i : i + w_len]
                ratio = difflib.SequenceMatcher(
                    None, clean_candidate.lower(), window.lower()
                ).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_slice = window
                    best_start = i
                    best_end = i + w_len

        if best_ratio >= min_similarity and best_slice:
            logger.debug(
                "Recovered verbatim slice via fuzzy alignment (ratio %.2f): '%s'",
                best_ratio,
                best_slice,
            )
            return True, best_slice, best_start, best_end

        # Failed all checks
        logger.warning(
            "Verbatim quote verification failed for candidate: '%s'", clean_candidate
        )
        return False, "", None, None
