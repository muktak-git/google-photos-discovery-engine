"""Cognitive memory signal extractor executing structured LLM extraction with quote verification."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from src.common.config import get_config
from src.common.llm_client import LLMClient
from src.common.logger import get_logger
from src.common.schemas import (
    FilteredConversationRecord,
    MemoryCueType,
    MemorySignalRecord,
    RememberedCue,
    SearchFailureMode,
)
from src.extraction.prompt_templates import (
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_prompt,
)
from src.extraction.validator import QuoteVerifier

logger = get_logger("Extraction.Extractor")


class CognitiveSignalExtractor:
    """Extracts structured cognitive memory recall signals and verifies verbatim evidence."""

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.config = get_config()
        self.llm_client = llm_client or LLMClient()
        self.validator = QuoteVerifier()

    def extract_record(
        self,
        record_id: str,
        source_text: str,
    ) -> MemorySignalRecord:
        """Extracts structured memory signal record with guaranteed verbatim quote validation."""
        clean_text = source_text.strip()
        prompt = build_extraction_prompt(clean_text)

        # Attempt structured LLM extraction
        try:
            raw_response = self.llm_client.generate_completion(
                prompt=prompt,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                json_mode=True,
                estimated_tokens=220,
            )

            parsed = json.loads(raw_response)
            if isinstance(parsed, dict) and "photo_type" in parsed:
                return self._build_validated_record(record_id, clean_text, parsed)
        except Exception as e:
            logger.warning(
                "LLM extraction error for record '%s': %s. Applying heuristic extraction fallback.",
                record_id,
                str(e),
            )

        # Heuristic fallback
        return self._heuristic_extraction(record_id, clean_text)

    def _build_validated_record(
        self, record_id: str, source_text: str, data: Dict[str, Any]
    ) -> MemorySignalRecord:
        """Parses LLM output dictionary into validated MemorySignalRecord."""
        # 1. Parse and align quote
        candidate_quote = str(data.get("verbatim_quote", "")).strip()
        is_valid, aligned_quote, start_idx, end_idx = self.validator.verify_and_align_quote(
            source_text, candidate_quote
        )

        if not is_valid:
            # Fallback: slice an authentic sentence containing failure or search
            aligned_quote, start_idx, end_idx = self._slice_fallback_quote(source_text)

        # 2. Parse remembered cues
        cues: List[RememberedCue] = []
        raw_cues = data.get("remembered_cues", [])
        if isinstance(raw_cues, list):
            for rc in raw_cues:
                if isinstance(rc, dict) and "detail" in rc:
                    c_type_str = str(rc.get("cue_type", "other")).lower()
                    try:
                        c_type = MemoryCueType(c_type_str)
                    except ValueError:
                        c_type = MemoryCueType.OTHER

                    cues.append(
                        RememberedCue(
                            cue_type=c_type,
                            detail=str(rc["detail"]).strip(),
                            is_negated=bool(rc.get("is_negated", False)),
                        )
                    )

        if not cues:
            cues.append(
                RememberedCue(
                    cue_type=MemoryCueType.OBJECT_SCENE,
                    detail=data.get("photo_type", "photo"),
                )
            )

        # 3. Parse failure mode
        f_mode_str = str(data.get("failure_mode", "zero_results")).lower()
        try:
            failure_mode = SearchFailureMode(f_mode_str)
        except ValueError:
            failure_mode = SearchFailureMode.SEMANTIC_DRIFT

        # 4. Parse frustration score
        try:
            score = int(data.get("user_frustration_score", 3))
            score = max(1, min(5, score))
        except (ValueError, TypeError):
            score = 3

        # 5. Photo type
        photo_type = str(data.get("photo_type", "photo")).strip() or "photo"

        # 6. Forgotten details and queries
        forgotten = [
            str(x).strip() for x in data.get("forgotten_details", []) if str(x).strip()
        ]
        queries = [
            str(x).strip() for x in data.get("attempted_queries", []) if str(x).strip()
        ]

        return MemorySignalRecord(
            record_id=record_id,
            source_text=source_text,
            photo_type=photo_type,
            remembered_cues=cues,
            forgotten_details=forgotten,
            attempted_queries=queries,
            failure_mode=failure_mode,
            user_frustration_score=score,
            verbatim_quote=aligned_quote,
            quote_char_start=start_idx,
            quote_char_end=end_idx,
        )

    def _slice_fallback_quote(
        self, source_text: str
    ) -> Tuple[str, Optional[int], Optional[int]]:
        """Extracts an exact, unaltered clause from source_text demonstrating the search struggle."""
        sentences = [s.strip() for s in re.split(r"[.!?]\s+", source_text) if s.strip()]
        for s in sentences:
            if any(
                k in s.lower()
                for k in ("search", "find", "looking", "typed", "zero", "nothing", "scroll")
            ):
                start = source_text.find(s)
                end = start + len(s) if start != -1 else None
                return s, start, end

        first_sentence = sentences[0] if sentences else source_text
        start = source_text.find(first_sentence)
        end = start + len(first_sentence) if start != -1 else None
        return first_sentence, start, end

    def _heuristic_extraction(
        self, record_id: str, source_text: str
    ) -> MemorySignalRecord:
        """Rule-based extractor used when LLM endpoint is unavailable."""
        lower = source_text.lower()

        # Identify photo type
        if "receipt" in lower or "bill" in lower or "invoice" in lower:
            photo_type = "receipt"
            primary_cue = MemoryCueType.DOCUMENT_OCR
            failure_mode = SearchFailureMode.OCR_FAILURE
        elif "screenshot" in lower:
            photo_type = "screenshot"
            primary_cue = MemoryCueType.DOCUMENT_OCR
            failure_mode = SearchFailureMode.OCR_FAILURE
        elif "password" in lower or "wifi" in lower or "sticker" in lower:
            photo_type = "sticker / document"
            primary_cue = MemoryCueType.DOCUMENT_OCR
            failure_mode = SearchFailureMode.OCR_FAILURE
        elif "yellow" in lower or "jacket" in lower or "red" in lower or "black" in lower:
            photo_type = "candid portrait"
            primary_cue = MemoryCueType.VISUAL_COLOR
            failure_mode = SearchFailureMode.SEMANTIC_DRIFT
        elif "pandemic" in lower or "summer" in lower or "college" in lower or "years ago" in lower:
            photo_type = "vacation / memory photo"
            primary_cue = MemoryCueType.TEMPORAL
            failure_mode = SearchFailureMode.ZERO_RESULTS
        else:
            photo_type = "general photo"
            primary_cue = MemoryCueType.OBJECT_SCENE
            failure_mode = SearchFailureMode.ZERO_RESULTS

        # Extract attempted queries from quotes
        queries = re.findall(r"['\"“]([^'\"”]{2,50})['\"”]", source_text)

        # Detect negation
        is_negated = "not smiling" in lower or "not wearing" in lower or "was not" in lower

        # Quote slice
        verbatim_quote, q_start, q_end = self._slice_fallback_quote(source_text)

        cues = [
            RememberedCue(
                cue_type=primary_cue,
                detail=photo_type,
                is_negated=is_negated,
            )
        ]

        return MemorySignalRecord(
            record_id=record_id,
            source_text=source_text,
            photo_type=photo_type,
            remembered_cues=cues,
            forgotten_details=["exact date / timestamp"],
            attempted_queries=queries,
            failure_mode=failure_mode,
            user_frustration_score=4,
            verbatim_quote=verbatim_quote,
            quote_char_start=q_start,
            quote_char_end=q_end,
        )
