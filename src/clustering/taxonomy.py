"""Problem taxonomy synthesizer and quantitative metric calculator."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.common.config import get_config
from src.common.logger import get_logger
from src.common.schemas import MemorySignalRecord, ProblemCluster, SearchFailureMode

logger = get_logger("Clustering.Taxonomy")


class TaxonomyBuilder:
    """Builds the retrieval problem taxonomy, computes metrics, and produces the 2x2 Problem Map."""

    def __init__(self) -> None:
        self.config = get_config()

    def build_taxonomy(
        self,
        cluster_map: Dict[str, List[int]],
        records: List[MemorySignalRecord],
    ) -> List[ProblemCluster]:
        """Synthesizes structured ProblemCluster entities with frequency, severity, and impact metrics."""
        total_records = len(records)
        if total_records == 0:
            return []

        clusters: List[ProblemCluster] = []

        for cid, indices in cluster_map.items():
            cluster_recs = [records[i] for i in indices]
            rec_count = len(cluster_recs)

            # 1. Frequency Score: proportion of total retrieval struggles
            frequency_score = round(rec_count / total_records, 3)

            # 2. Severity Score: mean user frustration score (1-5)
            severity_score = round(
                sum(r.user_frustration_score for r in cluster_recs) / rec_count, 2
            )

            # 3. Retrieval Impact Index = frequency * severity
            impact_index = round(frequency_score * severity_score, 3)

            # 4. Predominant failure mode
            failure_modes = [r.failure_mode for r in cluster_recs]
            mode_counter = Counter(failure_modes)
            primary_mode = mode_counter.most_common(1)[0][0]

            # 5. Associated photo types
            photo_types = sorted(list(set(r.photo_type for r in cluster_recs)))

            # 6. Representative cues
            cues_list = []
            for r in cluster_recs:
                for c in r.remembered_cues:
                    prefix = "not " if c.is_negated else ""
                    cues_list.append(f"{prefix}{c.detail}")
            top_cues = [c[0] for c in Counter(cues_list).most_common(5)]

            # 7. Curated top verbatim quotes
            quotes = [r.verbatim_quote for r in cluster_recs if r.verbatim_quote]

            # 8. Synthesize title and cognitive description
            title, description = self._synthesize_title_and_description(
                photo_types, primary_mode, top_cues
            )

            cluster_obj = ProblemCluster(
                cluster_id=cid,
                cluster_title=title,
                description=description,
                primary_failure_mode=primary_mode,
                photo_types=photo_types,
                record_count=rec_count,
                frequency_score=frequency_score,
                severity_score=severity_score,
                retrieval_impact_index=impact_index,
                sample_record_ids=[r.record_id for r in cluster_recs[:5]],
                representative_cues=top_cues,
                top_verbatim_quotes=quotes[:5],
            )
            clusters.append(cluster_obj)

        # Sort clusters by Retrieval Impact Index descending
        clusters.sort(key=lambda c: c.retrieval_impact_index, reverse=True)
        return clusters

    def _synthesize_title_and_description(
        self,
        photo_types: List[str],
        failure_mode: SearchFailureMode,
        top_cues: List[str],
    ) -> Tuple[str, str]:
        """Generates clear archetypal title and root cognitive breakdown description."""
        pt_str = ", ".join(photo_types).lower()

        if failure_mode == SearchFailureMode.OCR_FAILURE:
            title = "Document OCR & Numerical Receipt Indexing Failure"
            desc = (
                "Users recall text-heavy media (receipts, stickers, bills, invoices) by prices, merchant names, "
                "or partial words. Search fails due to unindexed small printed/handwritten text or currency symbols."
            )
        elif failure_mode == SearchFailureMode.SEMANTIC_DRIFT:
            title = "Visual Attribute & Color-Scene Semantic Mismatch"
            desc = (
                "Users recall salient visual cues (clothing colors, background structures, or negated attributes like 'not smiling'). "
                "Search produces semantic drift (e.g. matching 'yellow jacket' to wasps or 'red barn' to red cars)."
            )
        elif failure_mode == SearchFailureMode.CHRONOLOGICAL_OVERLOAD:
            title = "Chronological Overload from Coarse Queries"
            desc = (
                "Users formulate broad memory queries yielding hundreds of chronological matches, forcing exhaustive manual scrolling "
                "through thousands of gallery photos without progressive refinement filters."
            )
        elif failure_mode == SearchFailureMode.FACIAL_GAP:
            title = "Unindexed Faces in Candid or Profile Angles"
            desc = (
                "Facial clustering models fail when subjects look sideways, wear sunglasses, or stand at a distance, "
                "preventing users from finding family members in candid memories."
            )
        else:
            title = "Relative Temporal & Anchor Query Breakdown"
            desc = (
                "Users recall life events via relative episodic memory ('right before the pandemic', 'summer after college'), "
                "which fails against rigid Gregorian calendar indices."
            )

        return title, desc

    def export_problem_map(
        self, clusters: List[ProblemCluster], output_path: Optional[Path] = None
    ) -> Path:
        """Exports the complete problem taxonomy and 2x2 priority matrix into JSON."""
        self.config.ensure_directories()
        target_path = output_path or (self.config.output_dir / "retrieval_problem_map.json")

        # Map clusters into 2x2 Quadrants
        # Thresholds: Median frequency and 3.5 severity
        quadrants: Dict[str, List[Dict[str, Any]]] = {
            "quadrant_1_core_opportunities": [],  # High Freq, High Sev
            "quadrant_2_quality_of_life": [],     # High Freq, Low Sev
            "quadrant_3_critical_blockers": [],   # Low Freq, High Sev
            "quadrant_4_niche_edge_cases": [],    # Low Freq, Low Sev
        }

        freq_median = (
            sorted(c.frequency_score for c in clusters)[len(clusters) // 2]
            if clusters
            else 0.25
        )

        cluster_dicts = []
        for c in clusters:
            c_dict = c.model_dump()
            is_high_freq = c.frequency_score >= freq_median
            is_high_sev = c.severity_score >= 3.5

            if is_high_freq and is_high_sev:
                quadrant = "quadrant_1_core_opportunities"
            elif is_high_freq and not is_high_sev:
                quadrant = "quadrant_2_quality_of_life"
            elif not is_high_freq and is_high_sev:
                quadrant = "quadrant_3_critical_blockers"
            else:
                quadrant = "quadrant_4_niche_edge_cases"

            c_dict["matrix_quadrant"] = quadrant
            quadrants[quadrant].append(c_dict)
            cluster_dicts.append(c_dict)

        payload = {
            "version": "1.0",
            "total_clusters": len(clusters),
            "clusters": cluster_dicts,
            "problem_map_quadrants": quadrants,
        }

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        logger.info(
            "Exported retrieval problem map with %d clusters to %s",
            len(clusters),
            target_path,
        )
        return target_path
