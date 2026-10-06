"""Semantic clustering engine with HDBSCAN, outlier soft-assignment, and mega-cluster splitting."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from src.common.config import get_config
from src.common.logger import get_logger
from src.common.schemas import MemorySignalRecord

logger = get_logger("Clustering.Clusterer")


class SemanticClusterer:
    """Clustering engine grouping signal vectors into distinct cognitive failure archetypes."""

    def __init__(
        self,
        min_cluster_size: Optional[int] = None,
        soft_assign_threshold: Optional[float] = None,
        mega_cluster_split_threshold: Optional[float] = None,
    ) -> None:
        self.config = get_config()
        self.min_cluster_size = (
            min_cluster_size
            if min_cluster_size is not None
            else self.config.hdbscan_min_cluster_size
        )
        self.soft_assign_threshold = (
            soft_assign_threshold
            if soft_assign_threshold is not None
            else self.config.outlier_soft_assign_threshold
        )
        self.mega_cluster_threshold = (
            mega_cluster_split_threshold
            if mega_cluster_split_threshold is not None
            else self.config.mega_cluster_split_threshold
        )

    def cluster_signals(
        self,
        vectors: np.ndarray,
        records: List[MemorySignalRecord],
    ) -> Dict[str, List[int]]:
        """Clusters vectors and returns mapping of {cluster_id: [record_indices]}."""
        n_samples = len(records)
        if n_samples == 0:
            return {}
        if n_samples == 1:
            return {"cluster_01": [0]}

        # If sample size is smaller than min_cluster_size, adapt min_cluster_size
        effective_min_size = max(2, min(self.min_cluster_size, n_samples // 2))

        # 1. Primary Clustering via HDBSCAN
        labels = self._run_hdbscan(vectors, effective_min_size)

        # 2. Edge Case 4.1: Soft-assign unclustered noise points (-1)
        labels = self._soft_assign_outliers(vectors, labels)

        # Build initial clusters mapping
        cluster_map: Dict[str, List[int]] = {}
        for idx, lbl in enumerate(labels):
            cid = f"cluster_{lbl:02d}" if lbl >= 0 else "cluster_unclassified"
            cluster_map.setdefault(cid, []).append(idx)

        # 3. Edge Case 4.2: Sub-cluster mega-clusters exceeding threshold
        cluster_map = self._split_mega_clusters(vectors, cluster_map, n_samples)

        # 4. Edge Case 4.3: Merge semantic synonym clusters with high similarity
        cluster_map = self._merge_synonym_clusters(vectors, records, cluster_map)

        # Re-index clusters cleanly (cluster_01, cluster_02, ...)
        clean_map = {}
        for new_idx, (old_k, indices) in enumerate(
            sorted(cluster_map.items(), key=lambda x: len(x[1]), reverse=True), start=1
        ):
            clean_map[f"cluster_{new_idx:02d}"] = indices

        logger.info(
            "Clustering complete: formed %d distinct problem clusters from %d records",
            len(clean_map),
            n_samples,
        )
        return clean_map

    def _run_hdbscan(self, vectors: np.ndarray, min_size: int) -> np.ndarray:
        """Runs HDBSCAN clustering or falls back to distance-based grouping."""
        try:
            import hdbscan

            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=min_size,
                min_samples=1,
                metric="euclidean",
                cluster_selection_epsilon=0.3,
            )
            labels = clusterer.fit_predict(vectors)
            return labels
        except Exception as e:
            logger.warning("HDBSCAN run exception: %s. Using cosine similarity clustering.", str(e))
            # Fallback distance threshold clustering
            return self._cosine_threshold_clustering(vectors, threshold=0.60)

    def _cosine_threshold_clustering(
        self, vectors: np.ndarray, threshold: float = 0.60
    ) -> np.ndarray:
        """Lightweight connected component clustering based on pairwise cosine similarity."""
        sim_matrix = cosine_similarity(vectors)
        n = len(vectors)
        labels = np.full(n, -1, dtype=int)
        current_label = 0

        for i in range(n):
            if labels[i] != -1:
                continue
            labels[i] = current_label
            for j in range(i + 1, n):
                if labels[j] == -1 and sim_matrix[i, j] >= threshold:
                    labels[j] = current_label
            current_label += 1

        return labels

    def _soft_assign_outliers(self, vectors: np.ndarray, labels: np.ndarray) -> np.ndarray:
        """Edge Case 4.1: Soft-assign noise points (-1) to the nearest valid cluster centroid."""
        valid_labels = sorted(list(set(l for l in labels if l >= 0)))
        if not valid_labels or -1 not in labels:
            return labels

        # Compute centroid for each valid cluster
        centroids = {
            l: np.mean(vectors[labels == l], axis=0, keepdims=True)
            for l in valid_labels
        }

        updated_labels = labels.copy()
        for idx in range(len(labels)):
            if labels[idx] == -1:
                point_vec = vectors[idx : idx + 1]
                best_sim = -1.0
                best_label = -1
                for l, cent in centroids.items():
                    sim = float(cosine_similarity(point_vec, cent)[0, 0])
                    if sim > best_sim:
                        best_sim = sim
                        best_label = l

                if best_sim >= self.soft_assign_threshold and best_label != -1:
                    logger.debug(
                        "Soft-assigned outlier index %d to cluster %d (similarity %.2f)",
                        idx,
                        best_label,
                        best_sim,
                    )
                    updated_labels[idx] = best_label

        return updated_labels

    def _split_mega_clusters(
        self,
        vectors: np.ndarray,
        cluster_map: Dict[str, List[int]],
        total_records: int,
    ) -> Dict[str, List[int]]:
        """Edge Case 4.2: Hierarchically splits mega-clusters exceeding 35% of total volume."""
        result_map: Dict[str, List[int]] = {}

        for cid, indices in cluster_map.items():
            proportion = len(indices) / total_records
            if proportion > self.mega_cluster_threshold and len(indices) >= 4:
                logger.info(
                    "Mega-cluster '%s' accounts for %.1f%% of volume (%d records). Splitting.",
                    cid,
                    proportion * 100,
                    len(indices),
                )
                sub_vectors = vectors[indices]
                sub_labels = self._cosine_threshold_clustering(sub_vectors, threshold=0.70)
                sub_groups: Dict[int, List[int]] = {}
                for sub_i, slbl in enumerate(sub_labels):
                    sub_groups.setdefault(slbl, []).append(indices[sub_i])

                if len(sub_groups) > 1:
                    for sub_k, sub_idxs in sub_groups.items():
                        result_map[f"{cid}_sub{sub_k}"] = sub_idxs
                    continue

            result_map[cid] = indices

        return result_map

    def _merge_synonym_clusters(
        self,
        vectors: np.ndarray,
        records: List[MemorySignalRecord],
        cluster_map: Dict[str, List[int]],
    ) -> Dict[str, List[int]]:
        """Edge Case 4.3: Merges clusters with cosine similarity >= 0.85 and shared failure mode."""
        cids = list(cluster_map.keys())
        if len(cids) <= 1:
            return cluster_map

        centroids = {cid: np.mean(vectors[indices], axis=0, keepdims=True) for cid, indices in cluster_map.items()}
        merged_map: Dict[str, List[int]] = {}
        merged_cids = set()

        for i, c1 in enumerate(cids):
            if c1 in merged_cids:
                continue
            merged_map[c1] = list(cluster_map[c1])

            for j in range(i + 1, len(cids)):
                c2 = cids[j]
                if c2 in merged_cids:
                    continue

                sim = float(cosine_similarity(centroids[c1], centroids[c2])[0, 0])
                # Check if they share the predominant failure mode
                mode1 = records[cluster_map[c1][0]].failure_mode
                mode2 = records[cluster_map[c2][0]].failure_mode

                if sim >= 0.85 and mode1 == mode2:
                    logger.info("Merging synonym clusters '%s' and '%s' (similarity %.2f)", c1, c2, sim)
                    merged_map[c1].extend(cluster_map[c2])
                    merged_cids.add(c2)

        return merged_map
