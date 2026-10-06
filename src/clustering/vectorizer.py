"""Multi-signal vectorizer converting cognitive signal records into dense semantic embeddings."""

from __future__ import annotations

from typing import List, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from src.common.config import get_config
from src.common.logger import get_logger
from src.common.schemas import MemorySignalRecord

logger = get_logger("Clustering.Vectorizer")


class SignalVectorizer:
    """Transforms MemorySignalRecord entities into normalized dense vector representations."""

    def __init__(self) -> None:
        self.config = get_config()
        self.tfidf = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
            token_pattern=r"(?u)\b\w[\w-]*\w\b|\b\w\b",
        )
        self.is_fitted = False

    @staticmethod
    def build_composite_text(record: MemorySignalRecord) -> str:
        """Constructs a composite semantic representation blending photo category, cues, failure mode, and quotes."""
        cues_tokens = []
        for c in record.remembered_cues:
            prefix = "not " if c.is_negated else ""
            cues_tokens.append(f"{c.cue_type.value}: {prefix}{c.detail}")
        cues_str = ", ".join(cues_tokens) if cues_tokens else "none"

        forgotten_str = ", ".join(record.forgotten_details) if record.forgotten_details else "none"
        queries_str = ", ".join(record.attempted_queries) if record.attempted_queries else "none"

        composite = (
            f"photo_type: {record.photo_type} | "
            f"failure_mode: {record.failure_mode.value} | "
            f"remembered_cues: {cues_str} | "
            f"forgotten_attributes: {forgotten_str} | "
            f"attempted_queries: {queries_str} | "
            f"verbatim_evidence: {record.verbatim_quote}"
        )
        return composite

    def fit_transform(self, records: List[MemorySignalRecord]) -> np.ndarray:
        """Fits vectorizer and transforms records into an L2-normalized dense matrix."""
        if not records:
            return np.empty((0, 0))

        corpus = [self.build_composite_text(r) for r in records]
        tfidf_matrix = self.tfidf.fit_transform(corpus)
        self.is_fitted = True

        dense_matrix = tfidf_matrix.toarray()
        normalized_vectors = normalize(dense_matrix, norm="l2")

        logger.info(
            "Vectorized %d signal records into embedding space of dimension %d",
            len(records),
            normalized_vectors.shape[1],
        )
        return normalized_vectors

    def transform(self, records: List[MemorySignalRecord]) -> np.ndarray:
        """Transforms records using the fitted vectorizer."""
        if not self.is_fitted:
            raise ValueError("SignalVectorizer must be fitted before calling transform().")

        corpus = [self.build_composite_text(r) for r in records]
        tfidf_matrix = self.tfidf.transform(corpus)
        return normalize(tfidf_matrix.toarray(), norm="l2")
