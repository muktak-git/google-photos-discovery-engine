"""Tier 1 heuristic and lexical pre-filter for conversation screening."""

from __future__ import annotations

import re
from typing import Optional, Tuple

from src.common.config import get_config
from src.common.logger import get_logger

logger = get_logger("Filtering.Heuristics")


class HeuristicFilter:
    """Fast lexical and pattern-based pre-filter to eliminate noise before semantic classification."""

    def __init__(self) -> None:
        self.config = get_config()
        self._compile_regexes()

    def _compile_regexes(self) -> None:
        """Pre-compile lexical and exclusion regex patterns."""
        # Retrieval verbs indicating search or navigation intent
        self._retrieval_verbs_re = re.compile(
            r"\b(find|finding|search|searching|searched|locate|locating|located|"
            r"retrieve|retrieving|retrieval|track down|looking for|look for|scroll|scrolling|scrolled|"
            r"browse|browsing|digging through|hunt for|hunting)\b",
            re.IGNORECASE,
        )

        # Media targets
        self._media_targets_re = re.compile(
            r"\b(photo|photos|picture|pictures|pic|pics|screenshot|screenshots|"
            r"image|images|receipt|receipts|video|videos|document|documents|scan|scans|"
            r"snapshot|camera roll|gallery|album)\b",
            re.IGNORECASE,
        )

        # Incomplete memory cues and cognitive recall indicators
        self._memory_cues_re = re.compile(
            r"\b(remember|remembered|remembering|forgot|forgotten|forget|vague|"
            r"can't recall|cannot recall|can't remember|cannot remember|years ago|back in|"
            r"summer of|wearing|somewhere in|lost track|know i took|taken in|taken back|"
            r"months ago|college|high school|vacation in|trip to|around the time|"
            r"before the|after the|not smiling|not wearing|yellow|blue|red|green|black)\b",
            re.IGNORECASE,
        )

        # Hard negative exclusions (Edge Case 2.1: sync issues, billing, device health, data loss)
        self._hard_negatives_re = re.compile(
            r"\b(billing|google one|subscription|refund|payment|charged|renew|"
            r"storage full|buy storage|storage limit|15 gb|100 gb|battery drain|phone overheats|"
            r"overheating|update ruined|ui update|deleted (?:my|all|half|[a-z]+)|"
            r"lost (?:my photos|them|everything) after (?:the )?update|"
            r"wiped (?:my )?(?:entire )?(?:library|account|photos|storage)|"
            r"didn't backup|backup failed|failed to backup|cloud (?:sync )?(?:was )?wiped|"
            r"empty library|disappeared from cloud|can't upload|stuck uploading)\b",
            re.IGNORECASE,
        )

        # Search usability bugs without cognitive memory struggle (app crash or slow speed)
        self._usability_bug_re = re.compile(
            r"\b(crash|crashes|crashing|freeze|freezes|freezing|force close|"
            r"laggy|lag|stutter|slow to load|takes 10 seconds to open)\b",
            re.IGNORECASE,
        )

    def evaluate(self, text: str) -> Tuple[bool, float, Optional[str]]:
        """Evaluate text against Tier 1 heuristic rules.

        Returns:
            (passes_tier1, heuristic_confidence_score, exclusion_reason)
        """
        if not text:
            return False, 0.0, "Empty content"

        # Edge Case 1.3: Micro-review length check
        clean_text = text.strip()
        word_count = len(clean_text.split())
        if (
            len(clean_text) < self.config.heuristic_min_char_len
            or word_count < self.config.heuristic_min_word_len
        ):
            return False, 0.0, "Micro-review: insufficient cognitive context"

        # Edge Case 2.1: Check hard negatives for permanent sync/cloud deletion or billing
        # Note: If the text also strongly mentions a specific memory struggle, we don't immediately reject,
        # but pure sync/loss complaints are rejected immediately.
        has_hard_negative = bool(self._hard_negatives_re.search(clean_text))
        has_retrieval_verb = bool(self._retrieval_verbs_re.search(clean_text))
        has_media_target = bool(self._media_targets_re.search(clean_text))
        has_memory_cue = bool(self._memory_cues_re.search(clean_text))

        # Check pure crash or usability complaints
        has_crash = bool(self._usability_bug_re.search(clean_text))
        if has_crash and not has_memory_cue:
            return False, 0.1, "Application stability issue unrelated to memory recall"

        if has_hard_negative:
            # Data loss / cloud sync deletion takes precedence over superficial recall keywords
            has_explicit_search_query = bool(re.search(r"['\"][^'\"]+['\"]", clean_text)) or "search query" in clean_text.lower()
            if not has_explicit_search_query:
                return False, 0.0, "Out of scope: Cloud backup, deletion, or billing issue"

        # Scoring heuristic presence
        score = 0.0
        if has_retrieval_verb:
            score += 0.35
        if has_media_target:
            score += 0.25
        if has_memory_cue:
            score += 0.40

        # Pass condition: Must have either (retrieval verb + media target) OR (memory cue + media target)
        passes = (has_retrieval_verb and has_media_target) or (
            has_memory_cue and (has_media_target or has_retrieval_verb)
        )

        if not passes:
            return False, score, "Missing co-occurrence of retrieval verbs, media targets, and memory cues"

        return True, min(score, 1.0), None
