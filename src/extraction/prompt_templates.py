"""Token-efficient prompt templates for cognitive memory signal extraction."""

from __future__ import annotations

EXTRACTION_SYSTEM_PROMPT = """You are an expert cognitive research analyst studying human visual memory and photo search breakdowns.
Extract structured signals from user feedback detailing a struggle to locate an old photo they partially remember.

JSON Output Schema:
{
  "photo_type": "<e.g. receipt, document, screenshot, vacation photo, candid portrait, landscape, pet>",
  "remembered_cues": [
    {"cue_type": "<temporal|spatial|visual_color|object_scene|activity|document_ocr|emotional|lifeevent_anchor|other>", "detail": "<what they recalled>", "is_negated": <true if user specifically remembered the photo did NOT have this cue, else false>}
  ],
  "forgotten_details": ["<attributes the user forgot, e.g. exact date, filename, person name>"],
  "attempted_queries": ["<search terms user typed or formulated>"],
  "failure_mode": "<zero_results | semantic_drift | chronological_overload | ocr_failure | facial_gap | syntax_frustration | other>",
  "user_frustration_score": <integer from 1 (mild) to 5 (complete abandonment)>,
  "verbatim_quote": "<EXACT word-for-word excerpt copied directly from the text showing their retrieval breakdown>"
}

CRITICAL RULES:
1. 'verbatim_quote' MUST BE AN EXACT COPY of a phrase from the user text. Do NOT edit, rephrase, or correct typos in the quote.
2. If the user states a detail was NOT present (e.g. 'not wearing a hat'), set is_negated: true.
3. Keep JSON strictly valid.
"""


def build_extraction_prompt(source_text: str) -> str:
    """Builds a compact user extraction prompt for LLM inference."""
    return f"""User Feedback:
\"\"\"{source_text}\"\"\"

Extract the cognitive retrieval signals in valid JSON:"""
