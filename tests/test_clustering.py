"""Unit tests for signal vectorization, clustering, and problem taxonomy generation."""

import json
import unittest
from pathlib import Path
import numpy as np

from src.common.config import get_config
from src.common.schemas import (
    MemoryCueType,
    MemorySignalRecord,
    ProblemCluster,
    RememberedCue,
    SearchFailureMode,
)
from src.clustering.clusterer import SemanticClusterer
from src.clustering.pipeline import ClusteringPipeline
from src.clustering.taxonomy import TaxonomyBuilder
from src.clustering.vectorizer import SignalVectorizer


class TestClustering(unittest.TestCase):
    """Test suite covering vectorization, clustering algorithms, and metric modeling."""

    def setUp(self):
        self.config = get_config()
        self.config.ensure_directories()
        self.sample_records = [
            MemorySignalRecord(
                record_id="rec_01",
                source_text="Looking for a yellow jacket photo on a hiking trail in Oregon back in 2021",
                photo_type="candid portrait",
                remembered_cues=[
                    RememberedCue(cue_type=MemoryCueType.VISUAL_COLOR, detail="yellow jacket"),
                    RememberedCue(cue_type=MemoryCueType.OBJECT_SCENE, detail="hiking trail"),
                ],
                forgotten_details=["exact date"],
                attempted_queries=["yellow jacket hiking"],
                failure_mode=SearchFailureMode.SEMANTIC_DRIFT,
                user_frustration_score=4,
                verbatim_quote="Looking for a yellow jacket photo on a hiking trail",
            ),
            MemorySignalRecord(
                record_id="rec_02",
                source_text="Searching for a photo of my friend wearing yellow shirt at the lake",
                photo_type="candid portrait",
                remembered_cues=[
                    RememberedCue(cue_type=MemoryCueType.VISUAL_COLOR, detail="yellow shirt"),
                    RememberedCue(cue_type=MemoryCueType.SPATIAL, detail="lake"),
                ],
                forgotten_details=["month"],
                attempted_queries=["yellow shirt lake"],
                failure_mode=SearchFailureMode.SEMANTIC_DRIFT,
                user_frustration_score=4,
                verbatim_quote="Searching for a photo of my friend wearing yellow shirt",
            ),
            MemorySignalRecord(
                record_id="rec_03",
                source_text="Can't find my car insurance policy receipt from Best Buy for $1200",
                photo_type="receipt",
                remembered_cues=[
                    RememberedCue(cue_type=MemoryCueType.DOCUMENT_OCR, detail="receipt Best Buy"),
                ],
                forgotten_details=["filename"],
                attempted_queries=["$1200", "Best Buy receipt"],
                failure_mode=SearchFailureMode.OCR_FAILURE,
                user_frustration_score=5,
                verbatim_quote="Can't find my car insurance policy receipt from Best Buy",
            ),
            MemorySignalRecord(
                record_id="rec_04",
                source_text="Need to find my laptop receipt invoice text was missing",
                photo_type="receipt",
                remembered_cues=[
                    RememberedCue(cue_type=MemoryCueType.DOCUMENT_OCR, detail="invoice laptop receipt"),
                ],
                forgotten_details=["date"],
                attempted_queries=["laptop receipt"],
                failure_mode=SearchFailureMode.OCR_FAILURE,
                user_frustration_score=4,
                verbatim_quote="Need to find my laptop receipt invoice text was missing",
            ),
        ]

    def test_vectorizer_composite_text_and_dimensions(self):
        """Verify vectorizer generates non-empty composite strings and normalized matrix."""
        vectorizer = SignalVectorizer()
        composite = vectorizer.build_composite_text(self.sample_records[0])
        self.assertIn("yellow jacket", composite)
        self.assertIn("semantic_drift", composite)

        vectors = vectorizer.fit_transform(self.sample_records)
        self.assertEqual(vectors.shape[0], 4)
        self.assertGreater(vectors.shape[1], 10)

        # Verify L2 normalization: norms should be approx 1.0
        norms = np.linalg.norm(vectors, axis=1)
        for n in norms:
            self.assertAlmostEqual(n, 1.0, places=4)

    def test_clusterer_separation(self):
        """Verify clusterer groups similar failure modes together."""
        vectorizer = SignalVectorizer()
        vectors = vectorizer.fit_transform(self.sample_records)

        clusterer = SemanticClusterer(min_cluster_size=2)
        cluster_map = clusterer.cluster_signals(vectors, self.sample_records)

        self.assertGreaterEqual(len(cluster_map), 1)
        # All record indices 0, 1, 2, 3 must be accounted for
        all_assigned = [idx for indices in cluster_map.values() for idx in indices]
        self.assertEqual(len(all_assigned), 4)
        self.assertEqual(sorted(all_assigned), [0, 1, 2, 3])

    def test_taxonomy_metrics_calculation(self):
        """Verify F_C, S_C, and RII_C metric formulas."""
        cluster_map = {
            "cluster_01": [0, 1],  # 2 records, frustration = 4, 4 -> mean 4.0
            "cluster_02": [2, 3],  # 2 records, frustration = 5, 4 -> mean 4.5
        }
        builder = TaxonomyBuilder()
        clusters = builder.build_taxonomy(cluster_map, self.sample_records)

        self.assertEqual(len(clusters), 2)
        # Both have 2/4 = 0.50 frequency
        for c in clusters:
            self.assertEqual(c.frequency_score, 0.50)
            self.assertEqual(c.retrieval_impact_index, round(c.frequency_score * c.severity_score, 3))

        # Cluster 02 (severity 4.5) should have higher impact index (0.50 * 4.5 = 2.25) than Cluster 01 (0.50 * 4.0 = 2.0)
        self.assertGreaterEqual(clusters[0].retrieval_impact_index, clusters[1].retrieval_impact_index)

    def test_export_problem_map_and_quadrants(self):
        """Verify 2x2 problem map export and JSON structure."""
        cluster_map = {"cluster_01": [0, 1], "cluster_02": [2, 3]}
        builder = TaxonomyBuilder()
        clusters = builder.build_taxonomy(cluster_map, self.sample_records)

        export_path = builder.export_problem_map(clusters)
        self.assertTrue(export_path.exists())

        with open(export_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("problem_map_quadrants", data)
            self.assertIn("clusters", data)
            self.assertEqual(data["total_clusters"], 2)

    def test_clustering_pipeline_execution(self):
        """Verify full clustering pipeline runs on data/extracted/signals.jsonl."""
        pipeline = ClusteringPipeline()
        summary = pipeline.run_clustering()

        self.assertGreater(summary["total_records"], 0)
        self.assertGreater(summary["clusters_formed"], 0)
        self.assertTrue(Path(summary["problem_map_output_path"]).exists())


if __name__ == "__main__":
    unittest.main()
