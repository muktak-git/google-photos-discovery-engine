"""Type-safe Pydantic data contracts for the Photo Retrieval Discovery Engine."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class RelevanceBucket(str, Enum):
    """Categorization buckets for initial conversation filtering."""

    RELEVANT_PARTIAL_MEMORY = "relevant_partial_memory"
    GENERAL_SEARCH_USABILITY = "general_search_usability"
    IRRELEVANT_NOISE = "irrelevant_noise"


class MemoryCueType(str, Enum):
    """Taxonomy of sensory, temporal, and contextual cues retained by users."""

    TEMPORAL = "temporal"
    SPATIAL = "spatial"
    VISUAL_COLOR = "visual_color"
    OBJECT_SCENE = "object_scene"
    ACTIVITY_EVENT = "activity"
    DOCUMENT_OCR = "document_ocr"
    EMOTIONAL = "emotional"
    LIFEEVENT_ANCHOR = "lifeevent_anchor"
    OTHER = "other"


class SearchFailureMode(str, Enum):
    """Taxonomy of failure modes when attempting to retrieve photos."""

    ZERO_RESULTS = "zero_results"
    SEMANTIC_DRIFT = "semantic_drift"
    CHRONOLOGICAL_OVERLOAD = "chronological_overload"
    OCR_FAILURE = "ocr_failure"
    FACIAL_GAP = "facial_gap"
    SYNTAX_FRUSTRATION = "syntax_frustration"
    OTHER = "other"


class RawConversationRecord(BaseModel):
    """Represents an un-sanitized conversation collected directly from a public source."""

    raw_id: str = Field(..., description="Unique raw record identifier")
    source: str = Field(..., description="Platform identifier (e.g. play_store, reddit)")
    timestamp: str = Field(..., description="ISO 8601 string or raw date format")
    raw_text: str = Field(..., min_length=1, description="Raw conversation content")
    source_url: Optional[str] = Field(None, description="Public thread or review URL")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Platform-specific metadata")


class SanitizedConversationRecord(BaseModel):
    """Represents a conversation after deterministic PII scrubbing."""

    record_id: str = Field(..., description="Sanitized record ID")
    raw_id: str = Field(..., description="Lineage reference to raw record ID")
    source: str = Field(..., description="Source platform name")
    timestamp: str = Field(..., description="Standardized timestamp")
    source_url: Optional[str] = Field(None, description="Source URL")
    sanitized_text: str = Field(..., min_length=1, description="Scrubbed text with masked entities")
    pii_detected: List[str] = Field(
        default_factory=list, description="List of entity types scrubbed (e.g. ['PERSON', 'EMAIL'])"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Supplementary metadata")


class FilteredConversationRecord(BaseModel):
    """Conversation classified by the intent and relevancy filter."""

    record_id: str = Field(..., description="Sanitized record identifier")
    source: str = Field(..., description="Source platform")
    timestamp: str = Field(..., description="Timestamp")
    source_url: Optional[str] = None
    sanitized_text: str = Field(..., description="Text content")
    relevance_bucket: RelevanceBucket = Field(..., description="Classified intent bucket")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    exclusion_reason: Optional[str] = Field(
        None, description="Explanation if rejected as noise or general search"
    )

    @property
    def is_relevant(self) -> bool:
        """Convenience property indicating if record represents a partial memory retrieval struggle."""
        return self.relevance_bucket == RelevanceBucket.RELEVANT_PARTIAL_MEMORY


class RememberedCue(BaseModel):
    """A granular visual or contextual cue recalled by the user."""

    cue_type: MemoryCueType = Field(..., description="Category of memory cue")
    detail: str = Field(..., min_length=1, description="Extracted detail (e.g. 'yellow jacket')")
    is_negated: bool = Field(
        default=False,
        description="True if user specifically stated the photo did NOT have this cue",
    )


class MemorySignalRecord(BaseModel):
    """Structured extraction of cognitive signals, failure points, and verbatim quotes."""

    record_id: str = Field(..., description="Associated sanitized conversation ID")
    source_text: str = Field(..., description="Full text from which signal was derived")
    photo_type: str = Field(..., description="Category of photo (e.g. screenshot, candid portrait)")
    remembered_cues: List[RememberedCue] = Field(
        default_factory=list, description="Cues the user recalled"
    )
    forgotten_details: List[str] = Field(
        default_factory=list, description="Attributes the user could not remember"
    )
    attempted_queries: List[str] = Field(
        default_factory=list, description="Search queries formulated by user"
    )
    failure_mode: SearchFailureMode = Field(..., description="Primary retrieval breakdown mode")
    user_frustration_score: int = Field(
        ..., ge=1, le=5, description="Frustration rating from 1 (mild) to 5 (abandonment)"
    )
    verbatim_quote: str = Field(
        ..., min_length=3, description="Exact unaltered excerpt from source text"
    )
    quote_char_start: Optional[int] = Field(None, description="Character start offset in source text")
    quote_char_end: Optional[int] = Field(None, description="Character end offset in source text")

    @model_validator(mode="after")
    def verify_quote_against_source(self) -> MemorySignalRecord:
        """Asserts that verbatim quote is an exact or whitespace-normalized substring of source_text."""
        if not self.verbatim_quote or not self.source_text:
            return self

        norm_quote = re.sub(r"\s+", " ", self.verbatim_quote.strip().lower())
        norm_source = re.sub(r"\s+", " ", self.source_text.strip().lower())

        if norm_quote not in norm_source:
            # Check for partial inclusion or raise validation error to guarantee 0% hallucination
            raise ValueError(
                f"Verbatim quote '{self.verbatim_quote}' could not be matched inside source text."
            )
        return self


class ProblemCluster(BaseModel):
    """Aggregated cluster representing a distinct retrieval problem archetype."""

    cluster_id: str = Field(..., description="Unique cluster identifier (e.g. 'cluster_01')")
    cluster_title: str = Field(..., description="Human-readable title of failure pattern")
    description: str = Field(..., description="Root cognitive cause and user friction analysis")
    primary_failure_mode: SearchFailureMode = Field(..., description="Predominant failure mode")
    photo_types: List[str] = Field(default_factory=list, description="Primary photo categories")
    record_count: int = Field(..., ge=0, description="Total count of conversations in cluster")
    frequency_score: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized proportion of total retrieval struggles"
    )
    severity_score: float = Field(
        ..., ge=1.0, le=5.0, description="Mean user frustration score (1-5)"
    )
    retrieval_impact_index: float = Field(
        ..., ge=0.0, description="Impact Index = frequency_score * severity_score"
    )
    sample_record_ids: List[str] = Field(
        default_factory=list, description="Sample conversation IDs"
    )
    representative_cues: List[str] = Field(
        default_factory=list, description="Salient cues commonly present in this cluster"
    )
    top_verbatim_quotes: List[str] = Field(
        default_factory=list, description="Curated list of verified user quotes"
    )
    matrix_quadrant: Optional[str] = Field(
        "quadrant_1_core_opportunities", description="Placement in 2x2 Problem Map"
    )


class OpportunityRanking(BaseModel):
    """Evaluated product or ML opportunity area with multi-factor scoring."""

    opportunity_id: str = Field(..., description="Unique opportunity identifier")
    opportunity_title: str = Field(..., description="Strategic opportunity title")
    target_cluster_ids: List[str] = Field(
        default_factory=list, description="Clusters directly mitigated by this opportunity"
    )
    description: str = Field(..., description="Actionable product/ML direction")
    impact_score: float = Field(
        ..., ge=1.0, le=5.0, description="Impact on search task completion (1-5)"
    )
    evidence_confidence: float = Field(
        ..., ge=1.0, le=5.0, description="Strength & volume of user evidence (1-5)"
    )
    ml_feasibility: float = Field(
        ..., ge=1.0, le=5.0, description="Engineering & ML feasibility (1-5)"
    )
    ux_addressability: float = Field(
        ..., ge=1.0, le=5.0, description="Ease of user expression via UX (1-5)"
    )
    composite_score: float = Field(
        ..., ge=0.0, le=5.0, description="Weighted composite score"
    )
    is_primary_recommendation: bool = Field(
        default=False, description="Whether this is the #1 recommended opportunity"
    )
    evidence_quote_ids: List[str] = Field(
        default_factory=list, description="Key supporting quote IDs"
    )

    @classmethod
    def calculate_composite_score(
        cls,
        impact: float,
        evidence: float,
        feasibility: float,
        ux: float,
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Calculates composite score using weighted formula."""
        w = weights or {
            "impact": 0.40,
            "evidence": 0.25,
            "feasibility": 0.20,
            "ux": 0.15,
        }
        score = (
            w["impact"] * impact
            + w["evidence"] * evidence
            + w["feasibility"] * feasibility
            + w["ux"] * ux
        )
        return round(score, 3)


class PipelineCheckpoint(BaseModel):
    """State tracking object for resume capability."""

    pipeline_run_id: str
    started_at: str
    last_completed_stage: Optional[str] = None
    records_ingested: int = 0
    records_sanitized: int = 0
    records_filtered: int = 0
    records_extracted: int = 0
    clusters_identified: int = 0
    is_complete: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
