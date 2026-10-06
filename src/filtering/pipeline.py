"""Two-tier filtering pipeline coordinator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.common.config import get_config
from src.common.logger import get_logger
from src.common.schemas import (
    FilteredConversationRecord,
    RelevanceBucket,
    SanitizedConversationRecord,
)
from src.filtering.classifier import IntentClassifier
from src.filtering.heuristics import HeuristicFilter

logger = get_logger("Filtering.Pipeline")


class FilteringPipeline:
    """Coordinates Tier 1 heuristic pre-filtering and Tier 2 semantic intent classification."""

    def __init__(self) -> None:
        self.config = get_config()
        self.heuristic_filter = HeuristicFilter()
        self.intent_classifier = IntentClassifier()

    def run_filtering(
        self,
        sanitized_input_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Runs the two-tier filter on sanitized records and persists output files."""
        self.config.ensure_directories()
        input_file = (
            sanitized_input_path
            or (self.config.sanitized_dir / "sanitized_conversations.jsonl")
        )

        if not input_file.exists():
            raise FileNotFoundError(f"Sanitized input file not found: {input_file}")

        retrieval_records: List[FilteredConversationRecord] = []
        excluded_records: List[FilteredConversationRecord] = []
        all_records: List[FilteredConversationRecord] = []

        total_processed = 0
        passed_tier1 = 0
        bucket_counts: Dict[str, int] = {
            RelevanceBucket.RELEVANT_PARTIAL_MEMORY.value: 0,
            RelevanceBucket.GENERAL_SEARCH_USABILITY.value: 0,
            RelevanceBucket.IRRELEVANT_NOISE.value: 0,
        }

        # Read sanitized records line-by-line
        with open(input_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                total_processed += 1
                raw_data = json.loads(line)
                sanitized_rec = SanitizedConversationRecord.model_validate(raw_data)

                # Tier 1: Lexical Heuristics Check
                pass_h, h_score, h_reason = self.heuristic_filter.evaluate(
                    sanitized_rec.sanitized_text
                )

                if not pass_h:
                    filtered_rec = FilteredConversationRecord(
                        record_id=sanitized_rec.record_id,
                        source=sanitized_rec.source,
                        timestamp=sanitized_rec.timestamp,
                        source_url=sanitized_rec.source_url,
                        sanitized_text=sanitized_rec.sanitized_text,
                        relevance_bucket=RelevanceBucket.IRRELEVANT_NOISE,
                        relevance_score=round(h_score, 3),
                        exclusion_reason=f"Tier 1 Rejected: {h_reason}",
                    )
                    excluded_records.append(filtered_rec)
                    all_records.append(filtered_rec)
                    bucket_counts[RelevanceBucket.IRRELEVANT_NOISE.value] += 1
                    continue

                passed_tier1 += 1

                # Tier 2: Intent Classification
                classified_rec = self.intent_classifier.classify_record(sanitized_rec)
                bucket_counts[classified_rec.relevance_bucket.value] += 1
                all_records.append(classified_rec)

                if classified_rec.is_relevant:
                    retrieval_records.append(classified_rec)
                else:
                    excluded_records.append(classified_rec)

        # Output paths
        retrieval_output_path = self.config.filtered_dir / "retrieval_conversations.jsonl"
        excluded_output_path = self.config.filtered_dir / "excluded_conversations.jsonl"
        master_output_path = self.config.filtered_dir / "all_filtered_records.jsonl"

        # Write partitioned records
        with open(retrieval_output_path, "w", encoding="utf-8") as f_ret:
            for r in retrieval_records:
                f_ret.write(r.model_dump_json() + "\n")

        with open(excluded_output_path, "w", encoding="utf-8") as f_ex:
            for r in excluded_records:
                f_ex.write(r.model_dump_json() + "\n")

        with open(master_output_path, "w", encoding="utf-8") as f_all:
            for r in all_records:
                f_all.write(r.model_dump_json() + "\n")

        yield_rate = (
            round((len(retrieval_records) / total_processed) * 100, 2)
            if total_processed > 0
            else 0.0
        )

        summary = {
            "total_processed": total_processed,
            "passed_tier1_heuristics": passed_tier1,
            "relevant_retrieval_records": len(retrieval_records),
            "excluded_records": len(excluded_records),
            "bucket_breakdown": bucket_counts,
            "yield_rate_percent": yield_rate,
            "retrieval_output_path": str(retrieval_output_path),
            "master_output_path": str(master_output_path),
        }

        logger.info(
            "Phase 2 Filtering Complete: %d processed, %d passed heuristics, %d relevant retrieval records (Yield: %.2f%%)",
            total_processed,
            passed_tier1,
            len(retrieval_records),
            yield_rate,
        )
        return summary
