"""Clustering pipeline coordinator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.common.config import get_config
from src.common.logger import get_logger
from src.common.schemas import MemorySignalRecord, ProblemCluster
from src.clustering.clusterer import SemanticClusterer
from src.clustering.taxonomy import TaxonomyBuilder
from src.clustering.vectorizer import SignalVectorizer

logger = get_logger("Clustering.Pipeline")


class ClusteringPipeline:
    """Orchestrates vectorization, semantic clustering, metric calculation, and problem map export."""

    def __init__(self) -> None:
        self.config = get_config()
        self.vectorizer = SignalVectorizer()
        self.clusterer = SemanticClusterer()
        self.taxonomy_builder = TaxonomyBuilder()

    def run_clustering(
        self,
        signals_input_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Loads signals, forms clusters, computes impact metrics, and exports retrieval_problem_map.json."""
        self.config.ensure_directories()
        input_file = (
            signals_input_path or (self.config.extracted_dir / "signals.jsonl")
        )

        if not input_file.exists():
            raise FileNotFoundError(f"Extracted signals file not found: {input_file}")

        records: List[MemorySignalRecord] = []
        with open(input_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                records.append(MemorySignalRecord.model_validate(json.loads(line)))

        if not records:
            logger.warning("No signal records available for clustering.")
            return {"total_records": 0, "clusters_formed": 0}

        # 1. Vectorize
        vectors = self.vectorizer.fit_transform(records)

        # 2. Cluster
        cluster_map = self.clusterer.cluster_signals(vectors, records)

        # 3. Build Taxonomy & Metrics
        clusters = self.taxonomy_builder.build_taxonomy(cluster_map, records)

        # 4. Export Deliverable
        output_path = self.taxonomy_builder.export_problem_map(clusters)

        summary = {
            "total_records": len(records),
            "clusters_formed": len(clusters),
            "problem_clusters": [
                {
                    "cluster_id": c.cluster_id,
                    "title": c.cluster_title,
                    "record_count": c.record_count,
                    "frequency_score": c.frequency_score,
                    "severity_score": c.severity_score,
                    "retrieval_impact_index": c.retrieval_impact_index,
                }
                for c in clusters
            ],
            "problem_map_output_path": str(output_path),
        }

        logger.info(
            "Phase 4 Clustering Complete: %d records partitioned into %d problem clusters",
            len(records),
            len(clusters),
        )
        return summary
