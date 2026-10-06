"""Tier 2 few-shot and rule-calibrated intent classifier."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from src.common.config import get_config
from src.common.logger import get_logger
from src.common.schemas import (
    FilteredConversationRecord,
    RelevanceBucket,
    SanitizedConversationRecord,
)

logger = get_logger("Filtering.Classifier")


class IntentClassifier:
    """Classifies conversation records into partial memory retrieval, search usability, or noise."""

    def __init__(self) -> None:
        self.config = get_config()
        self._compile_classifier_rules()

    def _compile_classifier_rules(self) -> None:
        """Compile regex rules capturing semantic boundaries for partial recall."""
        # Vague/partial visual memory markers: colors, clothing, background, setting, objects
        self._visual_cues_re = re.compile(
            r"\b(wearing|shirt|jacket|hoodie|hat|dress|color|yellow|blue|red|green|black|white|"
            r"background|standing in front of|near|next to|beach|lake|mountain|barn|trail|"
            r"car|dog|cat|sunset|tree|river|sideways|turned away)\b",
            re.IGNORECASE,
        )

        # Document/OCR/text-in-image memory markers: receipts, screenshots, handwritten notes, stickers
        self._ocr_cues_re = re.compile(
            r"\b(receipt|receipts|invoice|bill|screenshot|screenshots|document|documents|"
            r"policy|sticker|password|wifi|text on the|ocr|read the text|wrote down|"
            r"amount|tax|price|dollar|\$)\b",
            re.IGNORECASE,
        )

        # Temporal fuzziness markers: seasons, relative events, unremembered dates
        self._temporal_fuzziness_re = re.compile(
            r"\b(don't remember the year|don't remember when|vaguely remember|back in|years ago|"
            r"summer of|college|graduation|pandemic|covid|before we moved|after the|"
            r"approximate|sometime in|around 20\d\d)\b",
            re.IGNORECASE,
        )

        # Search formulation failure or active retrieval intent markers
        self._retrieval_intent_re = re.compile(
            r"\b(looking for|look for|trying to find|try to find|trying to locate|how to find|"
            r"how do i find|how do i search|how to search|searched|search|searching|typed|typing|"
            r"nothing comes up|zero results|brings up nothing|gives me random|gives random|"
            r"instead of|scroll forever|manually scroll|scrolled through|"
            r"algorithm is (?:totally|completely)? (?:blind|oblivious|broken)|"
            r"can't find|cannot find|couldn't find|unable to find|lost track)\b",
            re.IGNORECASE,
        )

        # Sarcasm or idiom without concrete details (Edge Case 2.3)
        self._pure_idiom_re = re.compile(
            r"\b(needle in a haystack|ask(?:ing)? a brick wall|joke|useless search|"
            r"search sucks|worst search ever)\b",
            re.IGNORECASE,
        )

        # General search UI complaints without cognitive recall breakdown
        self._general_search_ui_re = re.compile(
            r"\b(search bar (?:position|placement|moved)|keyboard covers search|"
            r"search button|voice search icon|autocomplete dropdown|slow search|"
            r"takes too long to search|search takes 5 seconds)\b",
            re.IGNORECASE,
        )

    def classify_text(self, text: str) -> Tuple[RelevanceBucket, float, Optional[str]]:
        """Classifies text into RelevanceBucket with confidence score and reason."""
        clean_text = text.strip()

        # Check for pure search UI usability complaints (out of cognitive scope)
        if self._general_search_ui_re.search(clean_text) and not (
            self._visual_cues_re.search(clean_text) or self._ocr_cues_re.search(clean_text)
        ):
            return (
                RelevanceBucket.GENERAL_SEARCH_USABILITY,
                0.85,
                "General search UI layout or latency issue, not an incomplete visual memory breakdown",
            )

        # Check for pure idiomatic sarcasm with no concrete photo/cue mentions (Edge Case 2.3)
        has_idiom = bool(self._pure_idiom_re.search(clean_text))
        has_visual = bool(self._visual_cues_re.search(clean_text))
        has_ocr = bool(self._ocr_cues_re.search(clean_text))
        has_temporal = bool(self._temporal_fuzziness_re.search(clean_text))
        has_retrieval = bool(self._retrieval_intent_re.search(clean_text))

        if has_idiom and not (has_visual or has_ocr or has_temporal):
            return (
                RelevanceBucket.IRRELEVANT_NOISE,
                0.20,
                "Rhetorical or sarcastic complaint without extractable memory cues or photo details",
            )

        # Evaluate cognitive recall signals
        has_cues = has_visual or has_ocr or has_temporal
        evidence_points = sum([has_visual, has_ocr, has_temporal, has_retrieval])

        # Check for specific search query attempts mentioned in quotes or phrasing
        has_query_mention = bool(
            re.search(r"(?:searched|typed|typing|search for)\s+['\"“][^'\"”]+['\"”]", clean_text, re.I)
        )
        if has_query_mention:
            evidence_points += 1

        # Determine bucket and score
        if has_retrieval and has_cues:
            confidence = min(0.75 + (evidence_points * 0.05), 0.98)
            return (
                RelevanceBucket.RELEVANT_PARTIAL_MEMORY,
                confidence,
                None,
            )
        elif has_retrieval and not has_cues:
            return (
                RelevanceBucket.GENERAL_SEARCH_USABILITY,
                0.60,
                "Search failure mentioned but lacks specific visual, temporal, or document memory cues",
            )
        else:
            return (
                RelevanceBucket.IRRELEVANT_NOISE,
                0.15,
                "No photo retrieval or memory failure identified",
            )

    def classify_record(
        self, record: SanitizedConversationRecord
    ) -> FilteredConversationRecord:
        """Classify a sanitized conversation record into a FilteredConversationRecord."""
        bucket, score, reason = self.classify_text(record.sanitized_text)

        return FilteredConversationRecord(
            record_id=record.record_id,
            source=record.source,
            timestamp=record.timestamp,
            source_url=record.source_url,
            sanitized_text=record.sanitized_text,
            relevance_bucket=bucket,
            relevance_score=round(score, 3),
            exclusion_reason=reason,
        )

    def generate_classification_prompt(self, text: str) -> str:
        """Generate a few-shot prompt for LLM-based verification if external LLM inference is invoked."""
        return f"""You are an expert cognitive research auditor evaluating user feedback about photo search.
Goal: Identify conversations where users struggle to retrieve a photo they remember but CANNOT precisely describe.

Classification Categories:
1. RELEVANT_PARTIAL_MEMORY: User describes trying to locate a photo from incomplete/vague memories (e.g. remembered a color, setting, rough time, or OCR document), and search failed to retrieve it.
2. GENERAL_SEARCH_USABILITY: User searched for an exact keyword or date and experienced a UI lag/crash, or dislikes the search bar UI.
3. IRRELEVANT_NOISE: Cloud sync bugs, deleted photos, billing, general praise, or unrelated app issues.

Feedback Text:
\"\"\"{text}\"\"\"

Classify the text into JSON format:
{{"relevance_bucket": "RELEVANT_PARTIAL_MEMORY | GENERAL_SEARCH_USABILITY | IRRELEVANT_NOISE", "confidence": 0.0-1.0, "reason": "concise explanation"}}
"""
