"""Centralized configuration management for the Photo Retrieval Discovery Engine."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


# Base paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
SANITIZED_DATA_DIR = DATA_DIR / "sanitized"
FILTERED_DATA_DIR = DATA_DIR / "filtered"
EXTRACTED_DATA_DIR = DATA_DIR / "extracted"
OUTPUT_DATA_DIR = DATA_DIR / "output"
LOGS_DIR = PROJECT_ROOT / "logs"


def _load_env_file() -> None:
    """Lightweight .env parser that loads environment variables without requiring external libraries."""
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass


_load_env_file()


@dataclass
class EngineConfig:
    """Application and pipeline configuration parameters."""

    # Project metadata
    app_name: str = "GooglePhotosEngine"
    version: str = "0.1.0"
    debug: bool = field(
        default_factory=lambda: os.getenv("PHOTO_ENGINE_DEBUG", "false").lower() == "true"
    )

    # Paths
    project_root: Path = PROJECT_ROOT
    data_dir: Path = DATA_DIR
    raw_dir: Path = RAW_DATA_DIR
    sanitized_dir: Path = SANITIZED_DATA_DIR
    filtered_dir: Path = FILTERED_DATA_DIR
    extracted_dir: Path = EXTRACTED_DATA_DIR
    output_dir: Path = OUTPUT_DATA_DIR
    logs_dir: Path = LOGS_DIR

    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("PHOTO_ENGINE_LOG_LEVEL", "INFO"))
    log_to_file: bool = True
    log_file_name: str = "engine.log"

    # LLM Provider Configuration (Primary: GROQ, Secondary/Fallback: Gemini)
    primary_llm_provider: str = field(
        default_factory=lambda: os.getenv("PRIMARY_LLM_PROVIDER", "groq").lower()
    )
    groq_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GROQ_API_KEY")
    )
    groq_model: str = field(
        default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    )
    gemini_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    )
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2000

    # Ingestion & Scraping limits
    max_records_per_source: int = 500
    ingestion_batch_size: int = 50
    rate_limit_delay_seconds: float = 1.0

    # Privacy & PII scrubbing
    enable_pii_scrubbing: bool = True
    anonymize_entities: tuple[str, ...] = (
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "LOCATION",
        "IP_ADDRESS",
        "CRYPTO",
        "IBAN_CODE",
        "US_SSN",
    )

    # Filtering parameters
    heuristic_min_char_len: int = 30
    heuristic_min_word_len: int = 6
    relevance_threshold: float = 0.70

    # Extraction parameters
    extraction_concurrency: int = 5
    extraction_max_retries: int = 3
    fuzzy_quote_match_threshold: float = 0.95

    # Clustering parameters
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    hdbscan_min_cluster_size: int = 5
    hdbscan_min_samples: int = 3
    umap_n_components: int = 5
    umap_n_neighbors: int = 15
    outlier_soft_assign_threshold: float = 0.72
    mega_cluster_split_threshold: float = 0.35

    # Opportunity scoring weights (sum = 1.0)
    weight_impact: float = 0.40
    weight_evidence: float = 0.25
    weight_feasibility: float = 0.20
    weight_ux: float = 0.15

    # Hard feasibility cutoff (1.0 to 5.0 scale)
    min_feasibility_gate: float = 1.5

    def ensure_directories(self) -> None:
        """Create necessary data and log directories if they do not exist."""
        for directory in [
            self.data_dir,
            self.raw_dir,
            self.sanitized_dir,
            self.filtered_dir,
            self.extracted_dir,
            self.output_dir,
            self.logs_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "app_name": self.app_name,
            "version": self.version,
            "debug": self.debug,
            "log_level": self.log_level,
            "llm": {
                "primary_provider": self.primary_llm_provider,
                "groq_model": self.groq_model,
                "groq_configured": bool(self.groq_api_key),
                "gemini_model": self.gemini_model,
                "gemini_configured": bool(self.gemini_api_key),
            },
            "paths": {
                "project_root": str(self.project_root),
                "data_dir": str(self.data_dir),
                "output_dir": str(self.output_dir),
            },
            "clustering": {
                "min_cluster_size": self.hdbscan_min_cluster_size,
                "embedding_model": self.embedding_model_name,
            },
            "weights": {
                "impact": self.weight_impact,
                "evidence": self.weight_evidence,
                "feasibility": self.weight_feasibility,
                "ux": self.weight_ux,
            },
        }


# Singleton config instance
_global_config: EngineConfig | None = None


def get_config() -> EngineConfig:
    """Retrieve the singleton EngineConfig instance."""
    global _global_config
    if _global_config is None:
        _global_config = EngineConfig()
        _global_config.ensure_directories()
    return _global_config
