"""Opportunity scoring, verbatim evidence indexing, and report synthesis."""

from src.synthesis.pipeline import SynthesisPipeline
from src.synthesis.quote_bank import EvidenceBankBuilder
from src.synthesis.ranking import OpportunityRanker
from src.synthesis.report_generator import ReportGenerator

__all__ = [
    "OpportunityRanker",
    "EvidenceBankBuilder",
    "ReportGenerator",
    "SynthesisPipeline",
]
