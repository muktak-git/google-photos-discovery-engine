"""Multi-factor opportunity scoring and ranking engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.common.config import get_config
from src.common.logger import get_logger
from src.common.schemas import (
    MemorySignalRecord,
    OpportunityRanking,
    ProblemCluster,
    SearchFailureMode,
)

logger = get_logger("Synthesis.Ranking")


class OpportunityRanker:
    """Ranks candidate product and ML opportunity areas based on evidence, impact, and feasibility."""

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        self.config = get_config()
        self.weights = weights or {
            "impact": self.config.weight_impact,          # 0.40
            "evidence": self.config.weight_evidence,      # 0.25
            "feasibility": self.config.weight_feasibility,# 0.20
            "ux": self.config.weight_ux,                  # 0.15
        }
        self.min_feasibility_gate = self.config.min_feasibility_gate  # 1.5

    def rank_opportunities(
        self,
        clusters: List[ProblemCluster],
        records: List[MemorySignalRecord],
        custom_candidates: Optional[List[OpportunityRanking]] = None,
    ) -> List[OpportunityRanking]:
        """Translates problem clusters into candidate opportunity spaces, evaluates them, and selects the #1 recommendation."""
        candidates = (
            custom_candidates
            if custom_candidates is not None
            else self._generate_candidate_opportunities(clusters, records)
        )
        if not candidates:
            return []

        # Sort with deterministic tie-breaking hierarchy (Edge Case 5.2):
        # 1. Composite Score descending
        # 2. Impact Score descending
        # 3. Evidence Confidence descending
        # 4. Feasibility descending
        sorted_candidates = sorted(
            candidates,
            key=lambda o: (
                o.composite_score,
                o.impact_score,
                o.evidence_confidence,
                o.ml_feasibility,
            ),
            reverse=True,
        )

        # Enforce Feasibility Gate (Edge Case 5.1):
        # The primary recommendation MUST pass the feasibility cutoff (feasibility >= min_feasibility_gate)
        primary_selected = False
        for opp in sorted_candidates:
            if not primary_selected and opp.ml_feasibility >= self.min_feasibility_gate:
                opp.is_primary_recommendation = True
                primary_selected = True
            else:
                opp.is_primary_recommendation = False

        primary_opp = next(
            (o for o in sorted_candidates if o.is_primary_recommendation),
            sorted_candidates[0] if sorted_candidates else None,
        )

        logger.info(
            "Ranked %d opportunities. Primary recommendation: '%s' (Composite score: %.2f)",
            len(sorted_candidates),
            primary_opp.opportunity_title if primary_opp else "None",
            primary_opp.composite_score if primary_opp else 0.0,
        )
        return sorted_candidates

    def _generate_candidate_opportunities(
        self,
        clusters: List[ProblemCluster],
        records: List[MemorySignalRecord],
    ) -> List[OpportunityRanking]:
        """Maps problem clusters into concrete, evidence-backed opportunity spaces."""
        opportunities: List[OpportunityRanking] = []
        cluster_by_mode = {c.primary_failure_mode: c for c in clusters}

        # Opportunity 1: Multi-Modal Visual Cue & Color-Scene Contrast Retrieval
        c_vis = cluster_by_mode.get(SearchFailureMode.SEMANTIC_DRIFT)
        evidence_conf_vis = min(5.0, 3.0 + (len(c_vis.sample_record_ids) * 0.5)) if c_vis else 3.5
        impact_vis = 4.8  # Directly targets core thesis (vague visual memory)
        feasibility_vis = 4.2  # Multi-modal CLIP/SigLIP fine-tuning on attribute-object binding is well-proven
        ux_vis = 4.5  # Natural language queries or color/scene pill filters

        score_vis = OpportunityRanking.calculate_composite_score(
            impact=impact_vis,
            evidence=evidence_conf_vis,
            feasibility=feasibility_vis,
            ux=ux_vis,
            weights=self.weights,
        )
        opportunities.append(
            OpportunityRanking(
                opportunity_id="opp_visual_contrast_search",
                opportunity_title="Multi-Modal Visual Cue & Color-Scene Contrast Retrieval",
                target_cluster_ids=[c_vis.cluster_id] if c_vis else ["cluster_01"],
                description=(
                    "Implement composition-aware multi-modal embeddings that bind colors and visual attributes "
                    "directly to subjects (e.g. 'friend wearing yellow jacket') while distinguishing between semantic "
                    "distractors (wasps vs yellow clothing) and respecting negative visual cues ('not smiling')."
                ),
                impact_score=impact_vis,
                evidence_confidence=evidence_conf_vis,
                ml_feasibility=feasibility_vis,
                ux_addressability=ux_vis,
                composite_score=score_vis,
                evidence_quote_ids=c_vis.sample_record_ids if c_vis else [],
            )
        )

        # Opportunity 2: High-Recall Document & Receipt Numerical Search Engine
        c_ocr = cluster_by_mode.get(SearchFailureMode.OCR_FAILURE)
        evidence_conf_ocr = min(5.0, 3.0 + (len(c_ocr.sample_record_ids) * 0.5)) if c_ocr else 3.8
        impact_ocr = 4.5  # Huge utility value for receipts, WiFi stickers, and tax documents
        feasibility_ocr = 4.6  # High ML feasibility via specialized on-device OCR token indexing
        ux_ocr = 4.0  # Document/receipt tab with dollar amount and merchant filters

        score_ocr = OpportunityRanking.calculate_composite_score(
            impact=impact_ocr,
            evidence=evidence_conf_ocr,
            feasibility=feasibility_ocr,
            ux=ux_ocr,
            weights=self.weights,
        )
        opportunities.append(
            OpportunityRanking(
                opportunity_id="opp_receipt_numerical_ocr",
                opportunity_title="High-Recall Document & Numerical Receipt OCR Engine",
                target_cluster_ids=[c_ocr.cluster_id] if c_ocr else ["cluster_02"],
                description=(
                    "Build dedicated optical recognition indexing for numbers, currency amounts ($1,249), "
                    "merchant logos, and handwritten text on utility stickers and receipts."
                ),
                impact_score=impact_ocr,
                evidence_confidence=evidence_conf_ocr,
                ml_feasibility=feasibility_ocr,
                ux_addressability=ux_ocr,
                composite_score=score_ocr,
                evidence_quote_ids=c_ocr.sample_record_ids if c_ocr else [],
            )
        )

        # Opportunity 3: Episodic Life-Event & Relative Temporal Search
        c_temp = cluster_by_mode.get(SearchFailureMode.ZERO_RESULTS)
        evidence_conf_temp = 3.8
        impact_temp = 4.2
        feasibility_temp = 3.5  # Temporal anchor graphs require personal calendar/event inference
        ux_temp = 4.2

        score_temp = OpportunityRanking.calculate_composite_score(
            impact=impact_temp,
            evidence=evidence_conf_temp,
            feasibility=feasibility_temp,
            ux=ux_temp,
            weights=self.weights,
        )
        opportunities.append(
            OpportunityRanking(
                opportunity_id="opp_relative_temporal_anchoring",
                opportunity_title="Episodic Life-Event & Relative Temporal Search",
                target_cluster_ids=[c_temp.cluster_id] if c_temp else ["cluster_03"],
                description=(
                    "Allow queries anchored to relative memory landmarks ('right before pandemic', 'summer after college') "
                    "by synthesizing chronological photo clusters into life-epoch clusters."
                ),
                impact_score=impact_temp,
                evidence_confidence=evidence_conf_temp,
                ml_feasibility=feasibility_temp,
                ux_addressability=ux_temp,
                composite_score=score_temp,
                evidence_quote_ids=c_temp.sample_record_ids if c_temp else [],
            )
        )

        # Opportunity 4: Conversational Faceted Refinement
        c_overload = cluster_by_mode.get(SearchFailureMode.CHRONOLOGICAL_OVERLOAD)
        impact_overload = 3.9
        feasibility_overload = 4.4
        ux_overload = 4.6
        evidence_conf_overload = 3.5

        score_overload = OpportunityRanking.calculate_composite_score(
            impact=impact_overload,
            evidence=evidence_conf_overload,
            feasibility=feasibility_overload,
            ux=ux_overload,
            weights=self.weights,
        )
        opportunities.append(
            OpportunityRanking(
                opportunity_id="opp_faceted_progressive_refinement",
                opportunity_title="Progressive Multi-Facet Memory Refinement",
                target_cluster_ids=[c_overload.cluster_id] if c_overload else ["cluster_04"],
                description=(
                    "When queries yield hundreds of results, prompt users with dynamic disambiguation chips "
                    "(e.g. 'Was it indoors or outdoors?', 'Were people present?') to prune chronological search spaces."
                ),
                impact_score=impact_overload,
                evidence_confidence=evidence_conf_overload,
                ml_feasibility=feasibility_overload,
                ux_addressability=ux_overload,
                composite_score=score_overload,
                evidence_quote_ids=c_overload.sample_record_ids if c_overload else [],
            )
        )

        return opportunities
